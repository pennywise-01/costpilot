from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# --- Widget type & metric enums ---

class WidgetType(str):
    STAT_CARD = "stat_card"
    AREA_CHART = "area_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    STACKED_AREA_CHART = "stacked_area_chart"
    TABLE = "table"
    PROGRESS_LIST = "progress_list"
    STATUS_LIST = "status_list"


VALID_WIDGET_TYPES = {
    WidgetType.STAT_CARD,
    WidgetType.AREA_CHART,
    WidgetType.BAR_CHART,
    WidgetType.PIE_CHART,
    WidgetType.STACKED_AREA_CHART,
    WidgetType.TABLE,
    WidgetType.PROGRESS_LIST,
    WidgetType.STATUS_LIST,
}

VALID_METRICS_BY_TYPE: dict[str, set[str]] = {
    WidgetType.STAT_CARD: {
        "monthly_spend", "last_month_spend", "forecast",
        "change_percent", "potential_savings", "recommendation_count",
        "cloud_account_count", "resource_count",
    },
    WidgetType.AREA_CHART: {"cost_trend"},
    WidgetType.BAR_CHART: {"cost_by_cloud", "cost_by_service", "cost_by_region"},
    WidgetType.PIE_CHART: {"cloud_distribution", "service_distribution"},
    WidgetType.STACKED_AREA_CHART: {"cost_trend_by_cloud"},
    WidgetType.TABLE: {"top_resources", "cloud_accounts", "recommendations"},
    WidgetType.PROGRESS_LIST: {"recommendation_categories", "pool_status"},
    WidgetType.STATUS_LIST: {"cloud_account_health"},
}

ALL_VALID_METRICS = set()
for _metrics in VALID_METRICS_BY_TYPE.values():
    ALL_VALID_METRICS.update(_metrics)


# --- Layout item ---

class LayoutItem(BaseModel):
    i: str = Field(min_length=1, max_length=64)
    x: int = Field(ge=0, lt=12)
    y: int = Field(ge=0, lt=1000)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=20)
    minW: int | None = Field(None, ge=1, le=12)
    minH: int | None = Field(None, ge=1, le=20)
    maxW: int | None = Field(None, ge=1, le=12)
    maxH: int | None = Field(None, ge=1, le=20)
    static: bool | None = None


# --- Widget config entry ---

class WidgetConfigEntry(BaseModel):
    type: str
    metric: str
    title: str | None = None
    color: str | None = None
    icon: str | None = None
    dateRange: int | None = Field(None, ge=1, le=365)
    groupBy: str | None = None
    smooth: bool | None = None
    params: dict[str, Any] | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_WIDGET_TYPES:
            raise ValueError(f"Unknown widget type: {v}")
        return v

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        # Metric is validated against the widget type in the full context
        if v not in ALL_VALID_METRICS:
            raise ValueError(f"Unknown metric: {v}")
        return v


# --- Dashboard CRUD schemas ---

class DashboardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9\s\-]+$")
    template_dashboard_id: str | None = None


class DashboardUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9\s\-]+$")
    layout_config: list[LayoutItem] | None = None
    widget_config: dict[str, WidgetConfigEntry] | None = None
    version: int = Field(..., description="Current version for optimistic locking")


class DashboardListItem(BaseModel):
    id: str
    name: str
    slug: str
    is_default: bool
    updated_by: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardDetail(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    is_default: bool
    layout_config: list[dict[str, Any]]
    previous_layout_config: list[dict[str, Any]] | None
    widget_config: dict[str, Any]
    version: int
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardDuplicate(BaseModel):
    name: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9\s\-]+$")


# --- Batch widget data schemas ---

class WidgetDataRequest(BaseModel):
    type: str
    metric: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_WIDGET_TYPES:
            raise ValueError(f"Unknown widget type: {v}")
        return v

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        if v not in ALL_VALID_METRICS:
            raise ValueError(f"Unknown metric: {v}")
        return v


class BatchWidgetDataRequest(BaseModel):
    widgets: list[WidgetDataRequest] = Field(..., max_length=30)


class BatchWidgetDataResponse(BaseModel):
    data: dict[str, Any]
    errors: dict[str, str]
    meta: dict[str, Any]
