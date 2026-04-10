"""Base class for Big Data Analytics connectors.

Provides common functionality for connectors that read from normalized
billing tables in analytics platforms (BigQuery, Redshift, Athena, Synapse)
instead of calling CSP APIs directly.
"""

import asyncio
import logging
import re
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.shared.enums import CloudType

logger = logging.getLogger(__name__)


class AnalyticsConfig:
    """Base configuration for analytics connectors."""
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.dataset_id: str | None = config.get("dataset_id") or config.get("database")
        self.table_name: str = config.get("table_name", "")
        self.schema_name: str | None = config.get("schema_name") or config.get("schema")
        self.query_template: str | None = config.get("query_template")
        self.custom_sql: str | None = config.get("custom_sql")
        
        # Timeout settings
        self.query_timeout: int = int(config.get("query_timeout", 120))
        self.connection_timeout: int = int(config.get("connection_timeout", 30))
    
    def get_fully_qualified_table(self) -> str:
        """Get fully qualified table name (platform-specific)."""
        raise NotImplementedError("Subclasses must implement this")
    
    def validate_required_fields(self, required: list[str]) -> None:
        """Validate that required config fields are present."""
        missing = [f for f in required if not self.config.get(f)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


class AnalyticsAdapterBase:
    """Base class for all analytics platform connectors.
    
    Subclasses must implement:
    - validate_credentials()
    - get_cost_and_usage()
    - get_monthly_cost_summary()
    - get_daily_costs()
    - discover_resources()
    """
    
    # Platform identifier
    platform_type: CloudType | None = None
    
    # Query timeout (seconds)
    DEFAULT_QUERY_TIMEOUT = 120
    DEFAULT_CONNECTION_TIMEOUT = 30
    
    def __init__(self, config: dict[str, Any]):
        """Initialize analytics adapter.
        
        Args:
            config: Decrypted configuration dict containing:
                - Platform-specific credentials
                - dataset_id/database: Dataset or database name
                - table_name: Normalized billing table name
                - schema/schema_name: Schema name (optional)
                - query_timeout: Max query execution time (default: 120s)
                - query_template: Custom SQL template (optional)
        """
        self.config = config
        self._analytics_config = self._build_config(config)
        self._client = None
        self._connection = None
    
    def _build_config(self, config: dict[str, Any]) -> AnalyticsConfig:
        """Build analytics config from raw config dict."""
        return AnalyticsConfig(config)
    
    @abstractmethod
    async def validate_credentials(self) -> dict[str, Any]:
        """Validate connection and credentials.
        
        Returns:
            dict with:
                - valid: bool
                - permission_warnings: list[str]
                - table_exists: bool (if checkable)
                - schema_valid: bool (if checkable)
        """
        pass
    
    @abstractmethod
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None
    ) -> dict[str, Any]:
        """Query normalized billing table for cost and usage data.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            granularity: DAILY or MONTHLY
            group_by: List of fields to group by (service, region, etc.)
        
        Returns:
            dict with:
                - columns: list[str]
                - rows: list[list[Any]]
                - cost_index: int (index of cost column)
                - date_index: int (index of date column)
        """
        pass
    
    @abstractmethod
    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get aggregated monthly cost summary.
        
        Returns:
            dict with:
                - this_month: float
                - last_month: float
                - forecast: float
        """
        pass
    
    @abstractmethod
    async def get_daily_costs(
        self,
        start_date: str,
        end_date: str,
        group_by: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get daily cost breakdown.
        
        Returns:
            list of dicts with:
                - date: str (YYYY-MM-DD)
                - cost: float
                - group_key: str (optional, if group_by specified)
        """
        pass
    
    @abstractmethod
    async def discover_resources(self) -> list[dict[str, Any]]:
        """Discover resources from normalized billing table.
        
        Returns:
            list of dicts with:
                - cloud_resource_id: str
                - name: str
                - resource_type: str
                - region: str
                - state: str
                - tags: dict
                - meta: dict (additional metadata)
        """
        pass
    
    @abstractmethod
    async def validate_table_schema(self) -> dict[str, Any]:
        """Validate that the normalized table has expected columns.
        
        Returns:
            dict with:
                - valid: bool
                - missing_columns: list[str]
                - extra_columns: list[str]
                - warnings: list[str]
        """
        pass
    
    async def close(self) -> None:
        """Close any open connections/clients."""
        if self._client:
            try:
                await self._close_client()
            except Exception:
                logger.warning(f"Error closing {self.platform_type} client")
            self._client = None
        
        if self._connection:
            try:
                await self._close_connection()
            except Exception:
                logger.warning(f"Error closing {self.platform_type} connection")
            self._connection = None
    
    @abstractmethod
    async def _close_client(self) -> None:
        """Close platform-specific client."""
        pass
    
    @abstractmethod
    async def _close_connection(self) -> None:
        """Close platform-specific connection."""
        pass
    
    # --- Utility Methods ---
    
    @staticmethod
    def sanitize_connection_error(error: Exception, config: dict) -> str:
        """Sanitize error messages to remove credentials.
        
        Removes:
        - AWS access keys (AKIA...)
        - GCP private keys
        - Azure client secrets
        - Passwords and tokens
        """
        msg = str(error)
        
        # AWS access keys
        msg = re.sub(r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]', msg)
        
        # GCP service account private keys
        msg = re.sub(r'"private_key":\s*"[^"]+"', '"private_key": "[REDACTED]"', msg)
        msg = re.sub(r"private_key['\"]?\s*[:=]\s*['\"]?[^'\"]+", "private_key: [REDACTED]", msg, flags=re.IGNORECASE)
        
        # Azure client secrets
        msg = re.sub(r'client_secret["\s]*[:=]\s*["\']?[\w\-/+=.]+', 'client_secret: [REDACTED]', msg, flags=re.IGNORECASE)
        
        # Generic password/secret patterns
        msg = re.sub(r'(?:password|secret|token)["\s]*[:=]\s*["\']?[\w\-/+=.]{8,}', '[REDACTED]', msg, flags=re.IGNORECASE)
        
        # Connection strings with embedded credentials
        msg = re.sub(r'://[^:]+:[^@]+@', '://[REDACTED]@[', msg)
        
        return msg
    
    @staticmethod
    def build_standard_query(
        table_ref: str,
        start_date: str,
        end_date: str,
        group_by: list[str] | None = None,
        custom_sql: str | None = None
    ) -> str:
        """Build standard SQL query for normalized billing table.
        
        Args:
            table_ref: Fully qualified table reference
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            group_by: Fields to group by
            custom_sql: Custom SQL template (overrides standard query)
        
        Returns:
            SQL query string with parameterized dates
        """
        if custom_sql:
            # Replace date placeholders in custom SQL
            return custom_sql.replace('@start_date', start_date).replace('@end_date', end_date)
        
        if group_by:
            group_fields = ", ".join(group_by)
            return f"""
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
        
        return f"""
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
    
    @staticmethod
    def parse_cost_row(row: dict | tuple | Any) -> dict[str, Any]:
        """Parse a cost row into standardized format.
        
        Handles both dict and tuple formats from different platforms.
        """
        if isinstance(row, dict):
            return {
                "date": str(row.get("usage_start_date") or row.get("invoice_month", "")),
                "cost": float(row.get("cost") or row.get("total_cost", 0)),
                "service": str(row.get("service_name", "")),
                "resource_type": str(row.get("resource_type", "")),
                "region": str(row.get("region", "")),
                "resource_count": int(row.get("resource_count", 0)),
            }
        
        # Tuple format — depends on query structure
        return {
            "date": str(row[0]) if len(row) > 0 else "",
            "cost": float(row[1]) if len(row) > 1 else 0,
        }
