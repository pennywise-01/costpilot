"""BigQuery connector for CostPilot.

Reads normalized cloud billing data from GCP BigQuery tables
instead of calling Cloud Billing API directly.

Use case: Enterprise users who export GCP billing data to BigQuery
and want CostPilot to query that normalized data.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core.exceptions import (
    GoogleAPIError,
    NotFound,
    Forbidden,
    BadRequest,
    RetryError
)

from app.cloud_accounts.adapters.analytics_base import AnalyticsAdapterBase, AnalyticsConfig
from app.shared.enums import CloudType
from app.shared.retry import with_retry, BIGQUERY_RETRY_CONFIG
from app.shared.circuit_breaker import bigquery_circuit_breaker
from app.shared.exceptions import BadRequestError, NotFoundError

logger = logging.getLogger(__name__)


class BigQueryConfig(AnalyticsConfig):
    """Configuration for BigQuery connector."""
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.project_id: str = config.get("project_id", "")
        self.dataset_id: str = config.get("dataset_id", "")
        self.service_account_key: str | None = config.get("service_account_key")
        self.location: str = config.get("location", "US")
        
        # Validate required fields
        self.validate_required_fields(["project_id", "dataset_id", "table_name"])
    
    def get_fully_qualified_table(self) -> str:
        """Get fully qualified table name: project.dataset.table"""
        return f"`{self.project_id}.{self.dataset_id}.{self.table_name}`"
    
    def get_credentials(self) -> service_account.Credentials | None:
        """Load service account credentials from config."""
        if not self.service_account_key:
            return None
        
        import json
        try:
            key_info = json.loads(self.service_account_key)
            return service_account.Credentials.from_service_account_info(key_info)
        except Exception as e:
            raise BadRequestError(f"Invalid service account key: {e}")


class BigQueryAdapter(AnalyticsAdapterBase):
    """Adapter for querying BigQuery billing export tables.
    
    Expected table schema (normalized):
    - invoice_month (STRING): YYYY-MM format
    - usage_start_date (DATE): When usage started
    - usage_end_date (DATE): When usage ended
    - cost (FLOAT): Cost in billing currency
    - currency (STRING): Currency code (USD, etc.)
    - service_name (STRING): e.g., "Compute Engine"
    - resource_type (STRING): e.g., "n1-standard-1"
    - region (STRING): e.g., "us-central1"
    - resource_id (STRING): Full resource identifier
    - project_name (STRING): GCP project name
    - tags (JSON): Resource tags
    - usage_amount (FLOAT): Quantity consumed
    - usage_unit (STRING): e.g., "bytes", "seconds"
    """
    
    platform_type = CloudType.BIGQUERY
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._config = BigQueryConfig(config)
        self._client: bigquery.Client | None = None
        self._client_lock = asyncio.Lock()
    
    async def _get_client(self) -> bigquery.Client:
        """Get or create BigQuery client."""
        async with self._client_lock:
            if self._client is None:
                credentials = self._config.get_credentials()
                if credentials:
                    self._client = bigquery.Client(
                        credentials=credentials,
                        project=self._config.project_id
                    )
                else:
                    # Use Application Default Credentials
                    self._client = bigquery.Client(
                        project=self._config.project_id
                    )
            return self._client
    
    async def validate_credentials(self) -> dict[str, Any]:
        """Validate BigQuery connection and table access."""
        try:
            client = await self._get_client()
            
            # Test connection with simple query
            test_query = f"""
                SELECT COUNT(*) as row_count
                FROM {self._config.get_fully_qualified_table()}
                LIMIT 1
            """
            
            query_job = client.query(test_query)
            result = list(query_job.result(timeout=self._config.connection_timeout))
            
            # Check table schema
            schema_valid = await self._check_table_schema(client)
            
            return {
                "valid": True,
                "table_exists": True,
                "schema_valid": schema_valid,
                "row_count": result[0].row_count if result else 0,
                "permission_warnings": []
            }
            
        except NotFound as e:
            return {
                "valid": False,
                "table_exists": False,
                "schema_valid": False,
                "error": f"Table not found: {e}",
                "permission_warnings": []
            }
        except Forbidden as e:
            return {
                "valid": False,
                "table_exists": None,
                "schema_valid": False,
                "error": f"Permission denied: {e}",
                "permission_warnings": [
                    "Service account needs roles/bigquery.dataViewer",
                    "Service account needs roles/bigquery.jobUser"
                ]
            }
        except Exception as e:
            return {
                "valid": False,
                "error": self.sanitize_connection_error(e, self.config),
                "permission_warnings": []
            }
    
    async def _check_table_schema(self, client: bigquery.Client) -> bool:
        """Validate that the table has expected columns."""
        try:
            table_ref = client.get_table(self._config.get_fully_qualified_table())
            columns = {schema.name.lower() for schema in table_ref.schema}
            
            # Check for minimum required columns
            required = {"cost", "usage_start_date"}
            return required.issubset(columns)
        except Exception:
            return False
    
    @bigquery_circuit_breaker.call
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None
    ) -> dict[str, Any]:
        """Query BigQuery for cost and usage data."""
        
        table_ref = self._config.get_fully_qualified_table()
        
        if group_by:
            # Custom grouping
            group_fields = ", ".join(group_by)
            query = f"""
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
            # Default: group by service and region
            query = f"""
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
        
        return await self._execute_query(query)
    
    @bigquery_circuit_breaker.call
    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get aggregated monthly cost summary from BigQuery."""
        table_ref = self._config.get_fully_qualified_table()
        
        now = datetime.now(timezone.utc)
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        next_month_start = this_month_start + timedelta(days=32)
        next_month_start = next_month_start.replace(day=1)
        
        query = f"""
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
            result = await self._execute_query(query)
            rows = result.get("rows", [])
            
            this_month = 0.0
            last_month = 0.0
            current_month_str = this_month_start.strftime('%Y-%m')
            last_month_str = last_month_start.strftime('%Y-%m')
            
            for row in rows:
                if isinstance(row, dict):
                    month = row.get("invoice_month", "")
                    cost = float(row.get("month_cost", 0))
                    if month == current_month_str:
                        this_month = cost
                    elif month == last_month_str:
                        last_month = cost
            
            # Simple forecast: extrapolate from current month
            days_elapsed = (now - this_month_start).days or 1
            days_in_month = (next_month_start - this_month_start).days
            forecast = (this_month / days_elapsed) * days_in_month if days_elapsed > 0 else 0.0
            
            return {
                "this_month": round(this_month, 2),
                "last_month": round(last_month, 2),
                "forecast": round(forecast, 2)
            }
            
        except Exception as e:
            logger.warning(f"BigQuery monthly cost summary failed: {e}")
            return {"this_month": 0.0, "last_month": 0.0, "forecast": 0.0}
    
    @bigquery_circuit_breaker.call
    async def get_daily_costs(
        self,
        start_date: str,
        end_date: str,
        group_by: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get daily cost breakdown from BigQuery."""
        table_ref = self._config.get_fully_qualified_table()
        
        if group_by and "service_name" in group_by:
            query = f"""
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
            query = f"""
                SELECT 
                    usage_start_date as date,
                    SUM(cost) as cost
                FROM {table_ref}
                WHERE usage_start_date >= '{start_date}' 
                  AND usage_start_date <= '{end_date}'
                GROUP BY 1
                ORDER BY date
            """
        
        result = await self._execute_query(query)
        return result.get("rows", [])
    
    @bigquery_circuit_breaker.call
    async def discover_resources(self) -> list[dict[str, Any]]:
        """Discover resources from BigQuery billing table."""
        table_ref = self._config.get_fully_qualified_table()
        
        query = f"""
            SELECT 
                resource_id as cloud_resource_id,
                COALESCE(resource_id, 'Unknown') as name,
                COALESCE(resource_type, 'Unknown') as resource_type,
                COALESCE(region, 'unknown') as region,
                'active' as state,
                '{}' as tags,
                project_name
            FROM {table_ref}
            WHERE resource_id IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5, 6, 7
            ORDER BY resource_id
            LIMIT 10000
        """
        
        result = await self._execute_query(query)
        rows = result.get("rows", [])
        
        resources = []
        for row in rows:
            if isinstance(row, dict):
                resources.append({
                    "cloud_resource_id": row.get("cloud_resource_id", ""),
                    "name": row.get("name", ""),
                    "resource_type": row.get("resource_type", ""),
                    "region": row.get("region", ""),
                    "state": row.get("state", "unknown"),
                    "tags": row.get("tags", {}),
                    "meta": {"project": row.get("project_name", "")}
                })
        
        return resources
    
    async def validate_table_schema(self) -> dict[str, Any]:
        """Validate BigQuery table schema."""
        try:
            client = await self._get_client()
            table_ref = client.get_table(self._config.get_fully_qualified_table())
            
            actual_columns = {schema.name.lower() for schema in table_ref.schema}
            
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
    
    async def _execute_query(self, query: str) -> dict[str, Any]:
        """Execute BigQuery query with timeout and error handling."""
        client = await self._get_client()
        
        try:
            query_job = client.query(
                query,
                job_config=bigquery.QueryJobConfig(
                    use_query_cache=True,
                    allow_large_results=False
                )
            )
            
            # Wait for query to complete with timeout
            rows = query_job.result(timeout=self._config.query_timeout)
            
            # Convert to list of dicts
            result_rows = []
            for row in rows:
                row_dict = dict(row)
                # Convert datetime objects to strings
                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                result_rows.append(row_dict)
            
            return {
                "columns": list(rows[0].keys()) if rows else [],
                "rows": result_rows,
                "total_rows": len(result_rows)
            }
            
        except asyncio.TimeoutError:
            query_job.cancel()
            raise TimeoutError(f"BigQuery query exceeded {self._config.query_timeout}s timeout")
        except Exception as e:
            sanitized_msg = self.sanitize_connection_error(e, self.config)
            logger.error(f"BigQuery query failed: {sanitized_msg}")
            raise BadRequestError(f"BigQuery query failed: {sanitized_msg}")
    
    async def _close_client(self) -> None:
        """Close BigQuery client."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
    
    async def _close_connection(self) -> None:
        """BigQuery doesn't use persistent connections."""
        pass
