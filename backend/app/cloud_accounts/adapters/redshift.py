"""AWS Redshift connector for CostPilot.

Reads normalized cloud billing data from AWS Redshift tables
using the Redshift Data API (serverless, no persistent connections).

Use case: Enterprise users who export AWS CUR (Cost and Usage Report)
to Redshift and want CostPilot to query that normalized data.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    ParamValidationError
)

from app.cloud_accounts.adapters.analytics_base import AnalyticsAdapterBase, AnalyticsConfig
from app.shared.enums import CloudType
from app.shared.retry import with_retry, REDSHIFT_RETRY_CONFIG
from app.shared.circuit_breaker import redshift_circuit_breaker
from app.shared.exceptions import BadRequestError

logger = logging.getLogger(__name__)


class RedshiftConfig(AnalyticsConfig):
    """Configuration for Redshift connector."""
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.cluster_id: str = config.get("cluster_id", "")
        self.database: str = config.get("database", "dev")
        self.host: str = config.get("host", "")
        self.port: int = int(config.get("port", 5439))
        self.region: str = config.get("region", "us-east-1")
        self.iam_access_key_id: str = config.get("iam_access_key_id", "")
        self.iam_secret_access_key: str = config.get("iam_secret_access_key", "")
        
        # Validate required fields
        required = ["database", "table_name"]
        if self.cluster_id:
            required.append("cluster_id")
        if self.host:
            required.append("host")
        self.validate_required_fields(required)
    
    def get_fully_qualified_table(self) -> str:
        """Get fully qualified table name: schema.table"""
        if self.schema_name:
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name
    
    def get_boto3_client(self) -> boto3.client:
        """Create Redshift Data API client."""
        session_kwargs = {"region_name": self.region}
        
        if self.iam_access_key_id and self.iam_secret_access_key:
            session_kwargs["aws_access_key_id"] = self.iam_access_key_id
            session_kwargs["aws_secret_access_key"] = self.iam_secret_access_key
        
        session = boto3.Session(**session_kwargs)
        return session.client("redshift-data")


class RedshiftAdapter(AnalyticsAdapterBase):
    """Adapter for querying Redshift billing tables via Data API.
    
    Uses Redshift Data API (serverless) - no persistent connections needed.
    
    Expected table schema (normalized):
    - invoice_month (VARCHAR): YYYY-MM format
    - usage_start_date (DATE): When usage started
    - usage_end_date (DATE): When usage ended
    - cost (DECIMAL): Cost in billing currency
    - currency (VARCHAR): Currency code (USD, etc.)
    - service_name (VARCHAR): e.g., "Amazon EC2"
    - resource_type (VARCHAR): e.g., "t3.medium"
    - region (VARCHAR): e.g., "us-east-1"
    - resource_id (VARCHAR): Full resource identifier (ARN)
    - project_name (VARCHAR): AWS account name / resource group
    - tags (SUPER): Resource tags (JSON)
    - usage_amount (DECIMAL): Quantity consumed
    - usage_unit (VARCHAR): e.g., "Bytes", "Seconds"
    """
    
    platform_type = CloudType.REDSHIFT
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._config = RedshiftConfig(config)
        self._client = None
        self._client_lock = asyncio.Lock()
    
    async def _get_client(self):
        """Get or create Redshift Data API client."""
        async with self._client_lock:
            if self._client is None:
                self._client = self._config.get_boto3_client()
            return self._client
    
    async def _execute_statement(self, sql: str) -> str:
        """Execute SQL statement and return statement ID."""
        client = await self._get_client()
        
        kwargs = {
            "Sql": sql,
            "Database": self._config.database
        }
        
        # Use cluster or secret ARN if configured
        if self._config.cluster_id:
            kwargs["ClusterIdentifier"] = self._config.cluster_id
        elif self._config.host:
            # For serverless, use SecretArn
            secret_arn = self._config.config.get("secret_arn")
            if secret_arn:
                kwargs["SecretArn"] = secret_arn
            else:
                kwargs["WorkgroupName"] = self._config.config.get("workgroup_name", "")
        
        response = client.execute_statement(**kwargs)
        return response["Id"]
    
    async def _get_statement_result(self, statement_id: str, timeout: int = 120) -> list[dict]:
        """Wait for statement to complete and fetch results."""
        client = await self._get_client()
        
        # Wait for statement to complete
        waiter = client.get_waiter("statement_complete")
        waiter.wait(
            Id=statement_id,
            WaiterConfig={"Delay": 2, "MaxAttempts": timeout // 2}
        )
        
        # Fetch results with pagination
        all_rows = []
        next_token = None
        
        while True:
            kwargs = {"Id": statement_id}
            if next_token:
                kwargs["NextToken"] = next_token
            
            response = client.get_statement_result(**kwargs)
            
            # Convert column metadata and rows to dicts
            columns = [col["name"] for col in response["ColumnMetadata"]]
            
            for row in response["Records"]:
                row_dict = {}
                for i, cell in enumerate(row):
                    # Extract value from the cell (could be different types)
                    value = None
                    for key in ["stringValue", "longValue", "doubleValue", "booleanValue"]:
                        if key in cell:
                            value = cell[key]
                            break
                    if i < len(columns):
                        row_dict[columns[i]] = value
                
                all_rows.append(row_dict)
            
            next_token = response.get("NextToken")
            if not next_token:
                break
        
        return all_rows
    
    @redshift_circuit_breaker.call
    async def validate_credentials(self) -> dict[str, Any]:
        """Validate Redshift connection and table access."""
        try:
            # Test with simple query
            table_ref = self._config.get_fully_qualified_table()
            sql = f"SELECT COUNT(*) as row_count FROM {table_ref} LIMIT 1"
            
            statement_id = await self._execute_statement(sql)
            await self._get_statement_result(statement_id, timeout=30)
            
            # Check schema
            schema_valid = await self._check_table_schema()
            
            return {
                "valid": True,
                "table_exists": True,
                "schema_valid": schema_valid,
                "permission_warnings": []
            }
            
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            
            if "AccessDenied" in error_code or "Unauthorized" in error_code:
                return {
                    "valid": False,
                    "error": f"Permission denied: {e}",
                    "permission_warnings": [
                        "IAM user needs redshift-data:ExecuteStatement",
                        "IAM user needs redshift-data:GetStatementResult",
                        "IAM user needs redshift-data:DescribeStatement"
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
    
    async def _check_table_schema(self) -> bool:
        """Validate table has required columns."""
        try:
            table_ref = self._config.get_fully_qualified_table()
            sql = f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = '{self._config.schema_name or 'public'}' 
                  AND table_name = '{self._config.table_name}'
            """
            
            statement_id = await self._execute_statement(sql)
            rows = await self._get_statement_result(statement_id, timeout=30)
            
            columns = {row.get("column_name", "").lower() for row in rows}
            required = {"cost", "usage_start_date"}
            
            return required.issubset(columns)
        except Exception:
            return False
    
    @redshift_circuit_breaker.call
    @with_retry(REDSHIFT_RETRY_CONFIG)
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None
    ) -> dict[str, Any]:
        """Query Redshift for cost and usage data."""
        
        table_ref = self._config.get_fully_qualified_table()
        
        if group_by:
            group_fields = ", ".join(group_by)
            sql = f"""
                SELECT 
                    {group_fields},
                    SUM(cost) as total_cost,
                    COUNT(DISTINCT resource_id) as resource_count
                FROM {table_ref}
                WHERE usage_start_date >= '{start_date}' 
                  AND usage_start_date <= '{end_date}'
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
                WHERE usage_start_date >= '{start_date}' 
                  AND usage_start_date <= '{end_date}'
                GROUP BY 1, 2, 3, 4
                ORDER BY total_cost DESC
            """
        
        statement_id = await self._execute_statement(sql)
        rows = await self._get_statement_result(statement_id, timeout=self._config.query_timeout)
        
        return {
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "total_rows": len(rows)
        }
    
    @redshift_circuit_breaker.call
    @with_retry(REDSHIFT_RETRY_CONFIG)
    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get aggregated monthly cost summary from Redshift."""
        table_ref = self._config.get_fully_qualified_table()
        
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
            statement_id = await self._execute_statement(sql)
            rows = await self._get_statement_result(statement_id, timeout=self._config.query_timeout)
            
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
            logger.warning(f"Redshift monthly cost summary failed: {e}")
            return {"this_month": 0.0, "last_month": 0.0, "forecast": 0.0}
    
    @redshift_circuit_breaker.call
    @with_retry(REDSHIFT_RETRY_CONFIG)
    async def get_daily_costs(
        self,
        start_date: str,
        end_date: str,
        group_by: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get daily cost breakdown from Redshift."""
        table_ref = self._config.get_fully_qualified_table()
        
        if group_by and "service_name" in group_by:
            sql = f"""
                SELECT 
                    usage_start_date as date,
                    service_name as group_key,
                    SUM(cost) as cost
                FROM {table_ref}
                WHERE usage_start_date >= '{start_date}' 
                  AND usage_start_date <= '{end_date}'
                GROUP BY 1, 2
                ORDER BY date, cost DESC
            """
        else:
            sql = f"""
                SELECT 
                    usage_start_date as date,
                    SUM(cost) as cost
                FROM {table_ref}
                WHERE usage_start_date >= '{start_date}' 
                  AND usage_start_date <= '{end_date}'
                GROUP BY 1
                ORDER BY date
            """
        
        statement_id = await self._execute_statement(sql)
        return await self._get_statement_result(statement_id, timeout=self._config.query_timeout)
    
    @redshift_circuit_breaker.call
    @with_retry(REDSHIFT_RETRY_CONFIG)
    async def discover_resources(self) -> list[dict[str, Any]]:
        """Discover resources from Redshift billing table."""
        table_ref = self._config.get_fully_qualified_table()
        
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
        
        statement_id = await self._execute_statement(sql)
        rows = await self._get_statement_result(statement_id, timeout=self._config.query_timeout)
        
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
        """Validate Redshift table schema."""
        try:
            table_ref = self._config.get_fully_qualified_table()
            sql = f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = '{self._config.schema_name or 'public'}' 
                  AND table_name = '{self._config.table_name}'
            """
            
            statement_id = await self._execute_statement(sql)
            rows = await self._get_statement_result(statement_id, timeout=30)
            
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
        """Redshift Data API doesn't use persistent clients."""
        self._client = None
    
    async def _close_connection(self) -> None:
        """Redshift Data API doesn't use persistent connections."""
        pass
