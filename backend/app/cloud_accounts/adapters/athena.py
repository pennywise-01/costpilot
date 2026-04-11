"""AWS Athena connector for CostPilot.

Reads normalized cloud billing data from AWS Athena tables
using the Athena Query API (async execution pattern).

Use case: Enterprise users who export AWS CUR (Cost and Usage Report)
to S3 and query it via Athena.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    ParamValidationError
)

from app.cloud_accounts.adapters.analytics_base import (
    AnalyticsAdapterBase, AnalyticsConfig,
    validate_sql_identifier, validate_query_params,
)
from app.shared.enums import CloudType
from app.shared.retry import with_retry, ATHENA_RETRY_CONFIG
from app.shared.circuit_breaker import athena_circuit_breaker
from app.shared.exceptions import BadRequestError

logger = logging.getLogger(__name__)


class AthenaConfig(AnalyticsConfig):
    """Configuration for Athena connector."""
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.database: str = config.get("database", "")
        self.workgroup: str = config.get("workgroup", "primary")
        self.s3_output_location: str = config.get("s3_output_location", "")
        self.region: str = config.get("region", "us-east-1")
        self.iam_access_key_id: str = config.get("iam_access_key_id", "")
        self.iam_secret_access_key: str = config.get("iam_secret_access_key", "")
        
        # Validate required fields
        self.validate_required_fields(["database", "table_name", "s3_output_location"])
    
    def get_fully_qualified_table(self) -> str:
        """Get fully qualified table name: database.table"""
        return f"{self.database}.{self.table_name}"
    
    def get_boto3_client(self) -> boto3.client:
        """Create Athena client."""
        session_kwargs = {"region_name": self.region}
        
        if self.iam_access_key_id and self.iam_secret_access_key:
            session_kwargs["aws_access_key_id"] = self.iam_access_key_id
            session_kwargs["aws_secret_access_key"] = self.iam_secret_access_key
        
        session = boto3.Session(**session_kwargs)
        return session.client("athena")


class AthenaAdapter(AnalyticsAdapterBase):
    """Adapter for querying Athena billing tables.
    
    Uses Athena Query API with async execution pattern:
    1. StartQueryExecution
    2. Poll GetQueryExecution until complete
    3. GetQueryResults (with pagination)
    
    Expected table schema (normalized from AWS CUR):
    - invoice_month (STRING): YYYY-MM format
    - usage_start_date (DATE): When usage started
    - usage_end_date (DATE): When usage ended
    - cost (DOUBLE): Cost in billing currency
    - currency (STRING): Currency code (USD, etc.)
    - service_name (STRING): e.g., "Amazon Elastic Compute Cloud"
    - resource_type (STRING): e.g., "t3.medium"
    - region (STRING): e.g., "us-east-1"
    - resource_id (STRING): Full resource ARN
    - project_name (STRING): AWS account name
    - tags (STRING): JSON-encoded tags
    - usage_amount (DOUBLE): Quantity consumed
    - usage_unit (STRING): e.g., "Bytes", "Seconds"
    """
    
    platform_type = CloudType.ATHENA
    
    # Athena polling config
    QUERY_POLL_INTERVAL = 2  # seconds
    QUERY_MAX_POLL_ATTEMPTS = 60  # max 120s at 2s intervals
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._config = AthenaConfig(config)
        self._client = None
        self._client_lock = asyncio.Lock()
    
    async def _get_client(self):
        """Get or create Athena client."""
        async with self._client_lock:
            if self._client is None:
                self._client = self._config.get_boto3_client()
            return self._client
    
    async def _start_query(self, sql: str) -> str:
        """Start Athena query and return QueryExecutionId."""
        client = await self._get_client()
        
        response = await asyncio.to_thread(
            client.start_query_execution,
            QueryString=sql,
            QueryExecutionContext={
                "Database": self._config.database
            },
            ResultConfiguration={
                "OutputLocation": self._config.s3_output_location
            },
            WorkGroup=self._config.workgroup,
        )
        
        return response["QueryExecutionId"]
    
    async def _wait_for_query(self, query_id: str, timeout: int = 120) -> str:
        """Wait for query to complete.
        
        Returns:
            Final state: "SUCCEEDED", "FAILED", "CANCELLED"
        """
        client = await self._get_client()
        start_time = time.time()
        
        for attempt in range(self.QUERY_MAX_POLL_ATTEMPTS):
            elapsed = time.time() - start_time
            if elapsed > timeout:
                # Cancel the query
                try:
                    await asyncio.to_thread(client.stop_query_execution, QueryExecutionId=query_id)
                except Exception:
                    pass
                raise TimeoutError(f"Athena query exceeded {timeout}s timeout")
            
            response = await asyncio.to_thread(client.get_query_execution, QueryExecutionId=query_id)
            state = response["QueryExecution"]["Status"]["State"]
            
            if state == "SUCCEEDED":
                return state
            elif state in ("FAILED", "CANCELLED"):
                reason = response["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
                raise BadRequestError(f"Athena query {state.lower()}: {self.sanitize_connection_error(Exception(reason), self.config)}")
            
            # Still running, wait before polling again
            await asyncio.sleep(self.QUERY_POLL_INTERVAL)
        
        raise TimeoutError(f"Athena query did not complete after {self.QUERY_MAX_POLL_ATTEMPTS} attempts")
    
    async def _get_query_results(self, query_id: str) -> list[dict]:
        """Fetch query results with pagination."""
        client = await self._get_client()
        all_rows = []
        next_token = None
        
        while True:
            kwargs = {"QueryExecutionId": query_id}
            if next_token:
                kwargs["NextToken"] = next_token
            
            response = await asyncio.to_thread(client.get_query_results, **kwargs)
            
            # First row is column headers
            if response["ResultSet"]["Rows"]:
                columns = [
                    var["VarCharValue"]
                    for var in response["ResultSet"]["Rows"][0]["Data"]
                    if "VarCharValue" in var
                ]
                
                # Convert data rows to dicts
                for row in response["ResultSet"]["Rows"][1:]:
                    row_dict = {}
                    for i, cell in enumerate(row["Data"]):
                        if i < len(columns) and "VarCharValue" in cell:
                            row_dict[columns[i]] = cell["VarCharValue"]
                        elif i < len(columns) and "BigIntValue" in cell:
                            row_dict[columns[i]] = int(cell["BigIntValue"])
                        elif i < len(columns) and "DoubleValue" in cell:
                            row_dict[columns[i]] = float(cell["DoubleValue"])
                    
                    all_rows.append(row_dict)
            
            next_token = response.get("NextToken")
            if not next_token:
                break
        
        return all_rows
    
    async def _execute_athena_query(self, sql: str, timeout: int = 120) -> list[dict]:
        """Execute Athena query with timeout."""
        query_id = await self._start_query(sql)
        await self._wait_for_query(query_id, timeout=timeout)
        return await self._get_query_results(query_id)
    
    async def validate_credentials(self) -> dict[str, Any]:
        """Validate Athena connection and table access."""
        try:
            # Test with simple query
            table_ref = validate_sql_identifier(
                self._config.get_fully_qualified_table(), "table reference"
            )
            sql = f"SELECT COUNT(*) as row_count FROM {table_ref} LIMIT 1"
            
            rows = await self._execute_athena_query(sql, timeout=30)
            
            return {
                "valid": True,
                "table_exists": True,
                "schema_valid": True,
                "permission_warnings": []
            }
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            
            if "AccessDenied" in error_code or "Unauthorized" in error_code:
                return {
                    "valid": False,
                    "error": f"Permission denied: {e}",
                    "permission_warnings": [
                        "IAM user needs athena:StartQueryExecution",
                        "IAM user needs athena:GetQueryExecution",
                        "IAM user needs athena:GetQueryResults",
                        "IAM user needs s3:GetObject and s3:PutObject for the configured S3 output location"
                    ]
                }
            
            return {
                "valid": False,
                "error": self.sanitize_connection_error(e, self.config),
                "permission_warnings": []
            }
        except Exception as e:
            return {
                "valid": False,
                "error": self.sanitize_connection_error(e, self.config),
                "permission_warnings": []
            }
    
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None
    ) -> dict[str, Any]:
        """Query Athena for cost and usage data."""
        validate_query_params(start_date, end_date, group_by)
        table_ref = validate_sql_identifier(
            self._config.get_fully_qualified_table(), "table reference"
        )
        
        if group_by:
            group_fields = ", ".join(group_by)
            sql = f"""
                SELECT 
                    {group_fields},
                    SUM(cost) as total_cost,
                    COUNT(DISTINCT resource_id) as resource_count
                FROM {table_ref}
                WHERE usage_start_date >= DATE('{start_date}')
                  AND usage_start_date <= DATE('{end_date}')
                GROUP BY {group_fields}
                ORDER BY total_cost DESC
            """
        else:
            sql = f"""
                SELECT 
                    invoice_month,
                    service_name,
                    resource_type,
                    region,
                    SUM(cost) as total_cost,
                    COUNT(DISTINCT resource_id) as resource_count
                FROM {table_ref}
                WHERE usage_start_date >= DATE('{start_date}')
                  AND usage_start_date <= DATE('{end_date}')
                GROUP BY 1, 2, 3, 4
                ORDER BY total_cost DESC
            """
        
        rows = await self._execute_athena_query(sql, timeout=self._config.query_timeout)
        
        return {
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "total_rows": len(rows)
        }
    
    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get aggregated monthly cost summary from Athena."""
        table_ref = validate_sql_identifier(
            self._config.get_fully_qualified_table(), "table reference"
        )
        
        now = datetime.now(timezone.utc)
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        next_month_start = this_month_start + timedelta(days=32)
        next_month_start = next_month_start.replace(day=1)
        
        sql = f"""
            SELECT 
                invoice_month,
                SUM(cost) as month_cost
            FROM {table_ref}
            WHERE invoice_month IN (
                '{this_month_start.strftime('%Y-%m')}',
                '{last_month_start.strftime('%Y-%m')}'
            )
            GROUP BY invoice_month
            ORDER BY invoice_month DESC
        """
        
        try:
            rows = await self._execute_athena_query(sql, timeout=self._config.query_timeout)
            
            this_month = 0.0
            last_month = 0.0
            current_month_str = this_month_start.strftime('%Y-%m')
            last_month_str = last_month_start.strftime('%Y-%m')
            
            for row in rows:
                month = row.get("invoice_month", "")
                cost = float(row.get("month_cost", 0))
                if month == current_month_str:
                    this_month = cost
                elif month == last_month_str:
                    last_month = cost
            
            # Forecast
            days_elapsed = (now - this_month_start).days or 1
            days_in_month = (next_month_start - this_month_start).days
            forecast = (this_month / days_elapsed) * days_in_month if days_elapsed > 0 else 0.0
            
            return {
                "this_month": round(this_month, 2),
                "last_month": round(last_month, 2),
                "forecast": round(forecast, 2)
            }
        except Exception as e:
            logger.warning(f"Athena monthly cost summary failed: {e}")
            return {"this_month": 0.0, "last_month": 0.0, "forecast": 0.0}
    
    async def get_daily_costs(
        self,
        start_date: str,
        end_date: str,
        group_by: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get daily cost breakdown from Athena."""
        validate_query_params(start_date, end_date, group_by)
        table_ref = validate_sql_identifier(
            self._config.get_fully_qualified_table(), "table reference"
        )
        
        if group_by and "service_name" in group_by:
            sql = f"""
                SELECT 
                    CAST(usage_start_date AS VARCHAR) as date,
                    service_name as group_key,
                    SUM(cost) as cost
                FROM {table_ref}
                WHERE usage_start_date >= DATE('{start_date}')
                  AND usage_start_date <= DATE('{end_date}')
                GROUP BY 1, 2
                ORDER BY date, cost DESC
            """
        else:
            sql = f"""
                SELECT 
                    CAST(usage_start_date AS VARCHAR) as date,
                    SUM(cost) as cost
                FROM {table_ref}
                WHERE usage_start_date >= DATE('{start_date}')
                  AND usage_start_date <= DATE('{end_date}')
                GROUP BY 1
                ORDER BY date
            """
        
        return await self._execute_athena_query(sql, timeout=self._config.query_timeout)
    
    async def discover_resources(self) -> list[dict[str, Any]]:
        """Discover resources from Athena billing table."""
        table_ref = validate_sql_identifier(
            self._config.get_fully_qualified_table(), "table reference"
        )
        
        sql = f"""
            SELECT 
                resource_id as cloud_resource_id,
                COALESCE(resource_id, 'Unknown') as name,
                COALESCE(resource_type, 'Unknown') as resource_type,
                COALESCE(region, 'unknown') as region,
                'active' as state,
                project_name
            FROM {table_ref}
            WHERE resource_id IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5, 6
            ORDER BY resource_id
            LIMIT 10000
        """
        
        rows = await self._execute_athena_query(sql, timeout=self._config.query_timeout)
        
        resources = []
        for row in rows:
            resources.append({
                "cloud_resource_id": row.get("cloud_resource_id", ""),
                "name": row.get("name", ""),
                "resource_type": row.get("resource_type", ""),
                "region": row.get("region", ""),
                "state": row.get("state", "unknown"),
                "tags": {},
                "meta": {"account": row.get("project_name", "")}
            })
        
        return resources
    
    async def validate_table_schema(self) -> dict[str, Any]:
        """Validate Athena table schema via information_schema."""
        try:
            schema_id = validate_sql_identifier(self._config.database, "database name")
            table_id = validate_sql_identifier(self._config.table_name, "table name")
            sql = f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = '{schema_id}' 
                  AND table_name = '{table_id}'
            """
            
            rows = await self._execute_athena_query(sql, timeout=30)
            actual_columns = {row.get("column_name", "").lower() for row in rows}
            
            expected_columns = {
                "invoice_month", "usage_start_date", "usage_end_date",
                "cost", "currency", "service_name", "resource_type",
                "region", "resource_id", "project_name"
            }
            
            missing = expected_columns - actual_columns
            extra = actual_columns - expected_columns
            
            return {
                "valid": len(missing) == 0,
                "missing_columns": list(missing),
                "extra_columns": list(extra),
                "warnings": [
                    f"Missing recommended column: {col}"
                    for col in missing
                ]
            }
        except Exception as e:
            return {
                "valid": False,
                "missing_columns": [],
                "extra_columns": [],
                "warnings": [f"Cannot validate schema: {e}"]
            }
    
    async def _close_client(self) -> None:
        """Athena doesn't use persistent clients."""
        self._client = None
    
    async def _close_connection(self) -> None:
        """Athena doesn't use persistent connections."""
        pass
