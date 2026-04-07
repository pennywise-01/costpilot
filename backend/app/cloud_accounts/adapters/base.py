"""Base classes for cloud provider adapters.

This module provides standardized base classes and mixins for cloud provider
adapters to reduce code duplication and ensure consistent behavior across
AWS, Azure, and GCP implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Protocol
import logging
import asyncio

from app.shared.exceptions import CloudProviderException
from app.shared.utils.time import utc_now


logger = logging.getLogger(__name__)


class CloudConfig(Protocol):
    """Protocol for cloud configuration."""
    def to_dict(self) -> dict[str, Any]: ...
    def validate(self) -> bool: ...


class ResourceDiscoveryResult:
    """Standardized resource discovery result.
    
    Provides a consistent data structure for resources discovered
    across all cloud providers.
    """

    def __init__(
        self,
        resource_id: str,
        resource_type: str,
        name: str,
        region: str | None = None,
        status: str = "unknown",
        tags: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        cost_per_month: float = 0.0
    ):
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.name = name
        self.region = region
        self.status = status
        self.tags = tags or {}
        self.metadata = metadata or {}
        self.created_at = created_at
        self.cost_per_month = cost_per_month

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.resource_id,
            "type": self.resource_type,
            "name": self.name,
            "region": self.region,
            "status": self.status,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "cost_per_month": self.cost_per_month
        }


class CostDataResult:
    """Standardized cost data result.
    
    Provides a consistent data structure for cost data retrieved
    from all cloud providers.
    """

    def __init__(
        self,
        date: datetime,
        cost: float,
        currency: str = "USD",
        service: str | None = None,
        resource_id: str | None = None,
        region: str | None = None,
        tags: dict[str, str] | None = None
    ):
        self.date = date
        self.cost = cost
        self.currency = currency
        self.service = service
        self.resource_id = resource_id
        self.region = region
        self.tags = tags or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "date": self.date.isoformat(),
            "cost": self.cost,
            "currency": self.currency,
            "service": self.service,
            "resource_id": self.resource_id,
            "region": self.region,
            "tags": self.tags
        }


class CloudAdapterBase(ABC):
    """Base class for all cloud adapters with common functionality.
    
    Provides standardized patterns for:
    - Client caching
    - Tag normalization
    - DateTime parsing
    - Pagination handling
    - Error logging
    """

    def __init__(self, provider_name: str, config: dict[str, Any]):
        self.provider_name = provider_name
        self.config = config
        self._client_cache: dict[str, Any] = {}
        self._logger = logging.getLogger(f"{__name__}.{provider_name}")

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate cloud credentials.
        
        Returns:
            True if credentials are valid
            
        Raises:
            CloudProviderException: If credentials are invalid
        """
        pass

    @abstractmethod
    async def get_regions(self) -> list[str]:
        """Get list of available regions."""
        pass

    @abstractmethod
    async def discover_resources(self) -> list[ResourceDiscoveryResult]:
        """Discover all resources across all regions."""
        pass

    @abstractmethod
    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None
    ) -> list[CostDataResult]:
        """Get cost and usage data.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: DAILY or MONTHLY
            group_by: List of dimensions to group by
            
        Returns:
            List of cost data results
        """
        pass

    @abstractmethod
    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get monthly cost summary.
        
        Returns:
            Dict with keys: this_month, last_month, forecast, change_percent
        """
        pass

    # Common utility methods

    def _get_cached_client(self, service_name: str, factory: callable) -> Any:
        """Get or create cached client for a service.
        
        Args:
            service_name: Name of the service (e.g., 'ec2', 's3')
            factory: Function to create client if not cached
            
        Returns:
            Cached or newly created client
        """
        if service_name not in self._client_cache:
            self._client_cache[service_name] = factory()
        return self._client_cache[service_name]

    def _clear_client_cache(self):
        """Clear all cached clients."""
        self._client_cache.clear()

    def _standardize_tags(self, tags: dict | list | None) -> dict[str, str]:
        """Standardize tag format across providers.
        
        AWS returns tags as list of {Key, Value} dicts
        Azure returns tags as dict
        GCP returns labels as dict
        
        Args:
            tags: Tags in provider-specific format
            
        Returns:
            Standardized dict of string key-value pairs
        """
        if tags is None:
            return {}

        if isinstance(tags, dict):
            return {str(k): str(v) for k, v in tags.items()}

        if isinstance(tags, list):
            # Handle AWS tag list format
            result = {}
            for tag in tags:
                if isinstance(tag, dict):
                    key = tag.get("Key") or tag.get("key")
                    value = tag.get("Value") or tag.get("value")
                    if key:
                        result[str(key)] = str(value) if value else ""
            return result

        return {}

    def _parse_datetime(self, dt_string: str | None) -> datetime | None:
        """Parse datetime string from various formats.
        
        Tries multiple formats commonly used by cloud providers.
        
        Args:
            dt_string: Datetime string to parse
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        if not dt_string:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                continue

        # Try ISO format
        try:
            return datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        except ValueError:
            pass

        self._logger.warning(f"Could not parse datetime: {dt_string}")
        return None

    async def _discover_with_pagination(
        self,
        fetch_page: callable,
        process_item: callable,
        max_results: int | None = None
    ) -> list[Any]:
        """Generic pagination handler for resource discovery.
        
        Args:
            fetch_page: Async function that takes next_token and returns (page, next_token)
            process_item: Async function to process each item
            max_results: Maximum number of results to return
            
        Returns:
            List of processed results
        """
        results = []
        next_token = None
        count = 0

        while True:
            page, next_token = await fetch_page(next_token)

            for item in page:
                processed = await process_item(item)
                if processed:
                    results.append(processed)
                    count += 1

                    if max_results and count >= max_results:
                        return results

            if not next_token:
                break

        return results


class RegionalDiscoveryMixin:
    """Mixin for adapters that discover resources by region.
    
    Provides parallel region discovery with concurrency control.
    """

    async def discover_resources_parallel(
        self,
        regions: list[str],
        discover_region: callable,
        max_concurrent: int = 5
    ) -> list[ResourceDiscoveryResult]:
        """Discover resources across regions in parallel with concurrency limit.
        
        Args:
            regions: List of regions to discover
            discover_region: Async function to discover resources in a region
            max_concurrent: Maximum number of concurrent region discoveries
            
        Returns:
            Combined list of resources from all regions
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def discover_with_limit(region: str):
            async with semaphore:
                try:
                    return await discover_region(region)
                except Exception as e:
                    logger.warning(f"Failed to discover resources in {region}: {e}")
                    return []

        tasks = [discover_with_limit(region) for region in regions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_resources = []
        for result in results:
            if isinstance(result, list):
                all_resources.extend(result)

        return all_resources


class CostDataMixin:
    """Mixin for cost data operations.
    
    Provides common cost calculation operations.
    """

    def calculate_monthly_summary(
        self,
        this_month_data: list[CostDataResult],
        last_month_data: list[CostDataResult]
    ) -> dict[str, float]:
        """Calculate monthly summary from cost data.
        
        Args:
            this_month_data: Cost data for current month
            last_month_data: Cost data for previous month
            
        Returns:
            Dict with this_month, last_month, forecast, and change_percent
        """
        this_month = sum(r.cost for r in this_month_data)
        last_month = sum(r.cost for r in last_month_data)

        # Calculate forecast
        today = utc_now().date()
        days_elapsed = max(today.day, 1)
        days_in_month = (
            (today.replace(day=1) + timedelta(days=32)).replace(day=1) -
            today.replace(day=1)
        ).days

        forecast = (this_month / days_elapsed) * days_in_month if days_elapsed > 0 else this_month

        change_percent = 0.0
        if last_month > 0:
            change_percent = ((this_month - last_month) / last_month) * 100

        return {
            "this_month": round(this_month, 2),
            "last_month": round(last_month, 2),
            "forecast": round(forecast, 2),
            "change_percent": round(change_percent, 2)
        }


class TagFilteringMixin:
    """Mixin for tag-based filtering.
    
    Provides utilities for filtering resources by tags.
    """

    def matches_tags(self, resource_tags: dict[str, str], filter_tags: dict[str, str]) -> bool:
        """Check if resource tags match filter criteria.
        
        Args:
            resource_tags: Tags on the resource
            filter_tags: Tags to filter by
            
        Returns:
            True if resource matches all filter tags
        """
        for key, value in filter_tags.items():
            if key not in resource_tags:
                return False
            if resource_tags[key] != value:
                return False
        return True

    def get_tag_value(self, tags: dict[str, str], *possible_keys: str) -> str | None:
        """Get tag value trying multiple possible key names.
        
        Useful when tag keys vary between providers (e.g., "Name" vs "name").
        
        Args:
            tags: Dictionary of tags
            possible_keys: Possible key names to try
            
        Returns:
            First matching tag value or None
        """
        for key in possible_keys:
            if key in tags:
                return tags[key]
            # Try case-insensitive match
            for tag_key in tags:
                if tag_key.lower() == key.lower():
                    return tags[tag_key]
        return None


# Backward compatibility alias
CloudAdapter = CloudAdapterBase
