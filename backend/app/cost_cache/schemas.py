"""Pydantic schemas for cost cache API.

These schemas define the request/response models for the cost cache endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CachedExpenseSummary(BaseModel):
    """Summary response with cache metadata."""

    model_config = ConfigDict(populate_by_name=True)

    this_month_total: float = Field(..., description="Total cost for current month")
    last_month_total: float = Field(..., description="Total cost for previous month")
    this_month_forecast: float = Field(..., description="Forecasted cost for current month")
    change_percent: float = Field(..., description="Percentage change from last month")

    # Cache metadata
    data_source: str = Field(
        default="cache",
        description="Source of data: 'cache', 'live', 'stale'"
    )
    cached_at: datetime | None = Field(
        default=None,
        description="When this data was cached"
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When this cache expires"
    )
    cache_age_hours: float | None = Field(
        default=None,
        description="Age of cache in hours"
    )


class CachedBreakdownItem(BaseModel):
    """Single item in cost breakdown."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name")
    type: str | None = Field(default=None, description="Item type (cloud, service, etc.)")
    total: float = Field(..., description="Total cost")
    previous_total: float = Field(default=0, description="Previous period cost")
    daily_breakdown: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Daily cost breakdown"
    )


class CachedExpenseBreakdown(BaseModel):
    """Breakdown response with cache metadata."""

    model_config = ConfigDict(populate_by_name=True)

    total: float = Field(..., description="Grand total cost")
    previous_total: float = Field(..., description="Previous period total")
    start_date: str = Field(..., description="Period start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Period end date (YYYY-MM-DD)")
    breakdown: list[CachedBreakdownItem] = Field(
        default_factory=list,
        description="Breakdown by category"
    )
    daily_totals: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Daily totals across all categories"
    )

    # Cache metadata
    data_source: str = Field(
        default="cache",
        description="Source of data: 'cache', 'live', 'stale'"
    )
    cached_at: datetime | None = Field(
        default=None,
        description="When this data was cached"
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When this cache expires"
    )


class CacheStatusResponse(BaseModel):
    """Cache health status response."""

    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(
        ...,
        description="Overall status: 'healthy', 'stale', 'expired', 'error', 'uninitialized'"
    )
    last_updated: datetime | None = Field(
        default=None,
        description="When cache was last successfully updated"
    )
    next_update: datetime | None = Field(
        default=None,
        description="When next update is scheduled"
    )
    accounts_cached: int = Field(
        default=0,
        description="Number of cloud accounts with cached data"
    )
    accounts_total: int = Field(
        default=0,
        description="Total number of cloud accounts"
    )
    is_refreshing: bool = Field(
        default=False,
        description="Whether a refresh is currently in progress"
    )
    last_error: str | None = Field(
        default=None,
        description="Last error message if failed"
    )


class CacheRefreshRequest(BaseModel):
    """Request to manually refresh cache."""

    force: bool = Field(
        default=False,
        description="Force refresh even if cache is not expired"
    )


class CacheRefreshResponse(BaseModel):
    """Response from cache refresh request."""

    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(
        ...,
        description="Status: 'refreshing', 'skipped', 'error'"
    )
    message: str = Field(..., description="Human-readable message")
    estimated_completion: datetime | None = Field(
        default=None,
        description="Estimated completion time"
    )
    refresh_id: str | None = Field(
        default=None,
        description="Unique ID for tracking this refresh"
    )


class CacheRefreshResult(BaseModel):
    """Internal result of cache refresh operation."""

    success: bool = Field(..., description="Whether refresh succeeded")
    accounts_total: int = Field(default=0, description="Total accounts processed")
    accounts_success: int = Field(default=0, description="Successfully refreshed")
    accounts_failed: int = Field(default=0, description="Failed to refresh")
    error_message: str | None = Field(default=None, description="Error if failed")
    this_month_total: float = Field(default=0, description="Aggregated this month cost")
    last_month_total: float = Field(default=0, description="Aggregated last month cost")
    forecast_total: float = Field(default=0, description="Aggregated forecast")


class CloudAccountCostCache(BaseModel):
    """Cost cache entry for a single cloud account."""

    model_config = ConfigDict(populate_by_name=True)

    cloud_account_id: str = Field(..., description="Cloud account ID")
    cloud_account_name: str = Field(..., description="Cloud account name")
    cloud_type: str = Field(..., description="Cloud provider type")
    this_month_total: float = Field(default=0, description="This month cost")
    last_month_total: float = Field(default=0, description="Last month cost")
    forecast_total: float = Field(default=0, description="Forecast cost")
    collected_at: datetime = Field(..., description="When data was collected")
    expires_at: datetime = Field(..., description="When cache expires")
    data_source: str = Field(default="live", description="Data source")
    error_message: str | None = Field(default=None, description="Error if failed")