"""Azure Synapse Analytics connector for CostPilot.

Reads normalized cloud billing data from Azure Synapse Analytics
using TDS protocol with Azure AD authentication.

Use case: Enterprise users who export Azure Cost Management data
to Synapse and want CostPilot to query that normalized data.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aioodbc
from azure.identity import ClientSecretCredential
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError
)

from app.cloud_accounts.adapters.analytics_base import AnalyticsAdapterBase, AnalyticsConfig
from app.shared.enums import CloudType
from app.shared.retry import with_retry, SYNAPSE_RETRY_CONFIG
from app.shared.circuit_breaker import synapse_circuit_breaker
from app.shared.exceptions import BadRequestError

logger = logging.getLogger(__name__)


class SynapseConfig(AnalyticsConfig):
    """Configuration for Synapse connector."""
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.server: str = config.get("server", "")
        self.database: str = config.get("database", "")
        self.tenant_id: str = config.get("tenant_id", "")
        self.client_id: str = config.get("client_id", "")
        self.client_secret: str = config.get("client_secret", "")
        self.port: int = int(config.get("port", 1433))
        
        # Validate required fields
        self.validate_required_fields(["server", "database", "tenant_id", "client_id", "client_secret"])
    
    def get_fully_qualified_table(self) -> str:
        """Get fully qualified table name: schema.table"""
        if self.schema_name:
            return f"{self.schema_name}.{self.table_name}"
        return f"dbo.{self.table_name}"
    
    def get_connection_string(self, access_token: str) -> str:
        """Build ODBC connection string with Azure AD token."""
        return (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={self.server},{self.port};"
            f"DATABASE={self.database};"
            f"UID=;"
            f"PWD=;"
            f"Authentication=ActiveDirectoryAccessToken;"
            f"ACCESSTOKEN={access_token};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
    
    async def get_access_token(self) -> str:
        """Get Azure AD access token for Synapse."""
        credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        # Synapse/SQL DB scope
        token = credential.get_token("https://database.windows.net/.default")
        return token.token


class SynapseAdapter(AnalyticsAdapterBase):
    """Adapter for querying Synapse billing tables.
    
    Uses Azure AD authentication with TDS protocol.
    
    Expected table schema (normalized):
    - invoice_month (VARCHAR): YYYY-MM format
    - usage_start_date (DATE): When usage started
    - usage_end_date (DATE): When usage ended
    - cost (DECIMAL): Cost in billing currency
    - currency (VARCHAR): Currency code (USD, etc.)
    - service_name (VARCHAR): e.g., "Virtual Machines"
    - resource_type (VARCHAR): e.g., "Standard_D2s_v3"
    - region (VARCHAR): e.g., "East US"
    - resource_id (VARCHAR): Full Azure resource ID
    - project_name (VARCHAR): Resource group / subscription name
    - tags (NVARCHAR): JSON-encoded tags
    - usage_amount (DECIMAL): Quantity consumed
    - usage_unit (VARCHAR): e.g., "1 Hour", "1 GB"
    """
    
    platform_type = CloudType.SYNAPSE
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._config = SynapseConfig(config)
        self._connection = None
        self._access_token = None
        self._token_lock = asyncio.Lock()
        self._conn_lock = asyncio.Lock()
    
    async def _get_access_token(self) -> str:
        """Get or refresh Azure AD access token."""
        async with self._token_lock:
            if self._access_token is None:
                self._access_token = await self._config.get_access_token()
            return self._access_token
    
    async def _get_connection(self) -> aioodbc.Connection:
        """Get or create database connection."""
        async with self._conn_lock:
            if self._connection is None or self._connection.closed:
                access_token = await self._get_access_token()
                conn_str = self._config.get_connection_string(access_token)
                self._connection = await aioodbc.connect(
                    dsn=conn_str,
                    timeout=self._config.connection_timeout
                )
            return self._connection
    
    async def _execute_query(self, sql: str, timeout: int = 120) -> list[dict]:
        """Execute SQL query and return results as list of dicts."""
        conn = await self._get_connection()
        async with conn.cursor() as cursor:
            cursor.set_query_timeout(timeout * 1000)  # Convert to milliseconds
            await cursor.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch all rows
            rows = await cursor.fetchall()
            
            # Convert to list of dicts
            result = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(columns):
                        # Convert datetime to string for JSON serialization
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        row_dict[columns[i]] = value
                result.append(row_dict)
            
            return result
    
    @synapse_circuit_breaker.call
    async def validate_credentials(self) -> dict[str, Any]:
        """Validate Synapse connection and table access."""
        try:
            # Test with simple query
            table_ref = self._config.get_fully_qualified_table()
            sql = f"SELECT COUNT(*) as row_count FROM {table_ref}"
            
            rows = await self._execute_query(sql, timeout=30)
            
            # Check schema
            schema_valid = await self._check_table_schema()
            
            return {
                "valid": True,
                "table_exists": True,
                "schema_valid": schema_valid,
                "permission_warnings": []
            }
            
        except ClientAuthenticationError as e:
            return {
                "valid": False,
                "error": f"Authentication failed: {e}",
                "permission_warnings": [
                    "Service principal needs 'Reader' role on subscription",
                    "Service principal needs 'db_datareader' role on Synapse database"
                ]
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
            sql = f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = '{self._config.schema_name or 'dbo'}' 
                  AND TABLE_NAME = '{self._config.table_name}'
            """
            
            rows = await self._execute_query(sql, timeout=30)
            columns = {row.get("COLUMN_NAME", "").lower() for row in rows}
            required = {"cost", "usage_start_date"}
            
            return required.issubset(columns)
        except Exception:
            return False
    
    @synapse_circuit_breaker.call
    @with_retry(SYNAPSE_RETRY_CONFIG)
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None
    ) -> dict[str, Any]:
        """Query Synapse for cost and usage data."""
        
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
        
        rows = await self._execute_query(sql, timeout=self._config.query_timeout)
        
        return {
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "total_rows": len(rows)
        }
    
    @synapse_circuit_breaker.call
    @with_retry(SYNAPSE_RETRY_CONFIG)
    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get aggregated monthly cost summary from Synapse."""
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
                N'{this_month_start.strftime('%Y-%m')}',
                N'{last_month_start.strftime('%Y-%m')}'
            )
            GROUP BY invoice_month
            ORDER BY invoice_month DESC
        """
        
        try:
            rows = await self._execute_query(sql, timeout=self._config.query_timeout)
            
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
            logger.warning(f"Synapse monthly cost summary failed: {e}")
            return {"this_month": 0.0, "last_month": 0.0, "forecast": 0.0}
    
    @synapse_circuit_breaker.call
    @with_retry(SYNAPSE_RETRY_CONFIG)
    async def get_daily_costs(
        self,
        start_date: str,
        end_date: str,
        group_by: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get daily cost breakdown from Synapse."""
        table_ref = self._config.get_fully_qualified_table()
        
        if group_by and "service_name" in group_by:
            sql = f"""
                SELECT 
                    CAST(usage_start_date AS VARCHAR) as date,
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
                    CAST(usage_start_date AS VARCHAR) as date,
                    SUM(cost) as cost
                FROM {table_ref}
                WHERE usage_start_date >= '{start_date}' 
                  AND usage_start_date <= '{end_date}'
                GROUP BY 1
                ORDER BY date
            """
        
        return await self._execute_query(sql, timeout=self._config.query_timeout)
    
    @synapse_circuit_breaker.call
    @with_retry(SYNAPSE_RETRY_CONFIG)
    async def discover_resources(self) -> list[dict[str, Any]]:
        """Discover resources from Synapse billing table."""
        table_ref = self._config.get_fully_qualified_table()
        
        sql = f"""
            SELECT 
                resource_id as cloud_resource_id,
                ISNULL(resource_id, 'Unknown') as name,
                ISNULL(resource_type, 'Unknown') as resource_type,
                ISNULL(region, 'unknown') as region,
                'active' as state,
                project_name
            FROM {table_ref}
            WHERE resource_id IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5, 6
            ORDER BY resource_id
        """
        
        rows = await self._execute_query(sql, timeout=self._config.query_timeout)
        
        resources = []
        for row in rows:
            resources.append({
                "cloud_resource_id": row.get("cloud_resource_id", ""),
                "name": row.get("name", ""),
                "resource_type": row.get("resource_type", ""),
                "region": row.get("region", ""),
                "state": row.get("state", "unknown"),
                "tags": {},
                "meta": {"subscription": row.get("project_name", "")}
            })
        
        return resources
    
    async def validate_table_schema(self) -> dict[str, Any]:
        """Validate Synapse table schema."""
        try:
            sql = f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = '{self._config.schema_name or 'dbo'}' 
                  AND TABLE_NAME = '{self._config.table_name}'
            """
            
            rows = await self._execute_query(sql, timeout=30)
            actual_columns = {row.get("COLUMN_NAME", "").lower() for row in rows}
            
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
        """Synapse doesn't use a separate client object."""
        pass
    
    async def _close_connection(self) -> None:
        """Close Synapse connection."""
        if self._connection and not self._connection.closed:
            try:
                await self._connection.close()
            except Exception:
                pass
        self._connection = None
        self._access_token = None
