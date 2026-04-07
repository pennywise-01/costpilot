"""Pydantic schemas for Data Export module."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enterprise.modules.export.enums import ExportDataType, ExportFormat, ExportStatus, DeliveryMethod


# ============== Column Definition ==============

class ExportColumn(BaseModel):
    """Column definition for export."""
    name: str
    label: str
    type: str = "string"  # string, number, currency, date, datetime, boolean, percentage
    format: str | None = None
    width: int | None = None


# ============== Filter Definitions ==============

class ExportFilter(BaseModel):
    """Filter configuration for exports."""
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, contains, in, between
    value: Any


# ============== Delivery Configuration ==============

class S3DeliveryConfig(BaseModel):
    """S3 delivery configuration."""
    method: Literal["s3"] = "s3"
    bucket: str
    region: str
    prefix: str = ""
    access_key_id: str | None = None
    secret_access_key: str | None = None


class GCSDeliveryConfig(BaseModel):
    """Google Cloud Storage delivery configuration."""
    method: Literal["gcs"] = "gcs"
    bucket: str
    prefix: str = ""
    service_account_key: str | None = None


class AzureBlobDeliveryConfig(BaseModel):
    """Azure Blob Storage delivery configuration."""
    method: Literal["azure_blob"] = "azure_blob"
    account_name: str
    container: str
    prefix: str = ""
    connection_string: str | None = None


class EmailDeliveryConfig(BaseModel):
    """Email delivery configuration."""
    method: Literal["email"] = "email"
    recipients: list[str]
    subject: str | None = None
    message: str | None = None


DeliveryConfig = S3DeliveryConfig | GCSDeliveryConfig | AzureBlobDeliveryConfig | EmailDeliveryConfig


# ============== Export Template Schemas ==============

class ExportTemplateCreate(BaseModel):
    """Create a new export template."""
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(None, max_length=1000)
    data_type: ExportDataType
    format: ExportFormat
    columns: list[ExportColumn] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    date_range_days: int | None = Field(None, ge=1, le=3650)
    group_by: list[str] | None = None
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "desc"
    is_public: bool = False


class ExportTemplateUpdate(BaseModel):
    """Update an export template."""
    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = Field(None, max_length=1000)
    columns: list[ExportColumn] | None = None
    filters: dict[str, Any] | None = None
    date_range_days: int | None = Field(None, ge=1, le=3650)
    group_by: list[str] | None = None
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] | None = None
    is_public: bool | None = None


class ExportTemplateResponse(BaseModel):
    """Export template response."""
    id: str
    organization_id: str
    name: str
    description: str | None
    data_type: ExportDataType
    format: ExportFormat
    columns: list[ExportColumn]
    filters: dict[str, Any]
    date_range_days: int | None
    group_by: list[str] | None
    sort_by: str | None
    sort_order: str
    created_by: str
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Export Job Schemas ==============

class ExportJobCreate(BaseModel):
    """Create a new export job."""
    name: str = Field(..., min_length=1, max_length=256)
    template_id: str | None = None
    data_type: ExportDataType
    format: ExportFormat
    columns: list[ExportColumn] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    group_by: list[str] | None = None
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "desc"
    delivery_config: DeliveryConfig | None = None


class ExportJobResponse(BaseModel):
    """Export job response."""
    id: str
    organization_id: str
    template_id: str | None
    name: str
    data_type: ExportDataType
    format: ExportFormat
    columns: list[ExportColumn]
    filters: dict[str, Any]
    date_range_start: datetime | None
    date_range_end: datetime | None
    group_by: list[str] | None
    sort_by: str | None
    sort_order: str | None
    status: ExportStatus
    progress_percent: float
    current_step: str | None
    total_records: int | None
    processed_records: int
    record_count: int | None
    file_size_bytes: int | None
    file_url: str | None
    error_message: str | None
    created_by: str
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    is_scheduled: bool
    created_at: datetime
    updated_at: datetime
    # Signed download token (SEC-14) — only populated on job creation
    download_token: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExportJobListResponse(BaseModel):
    """Paginated export job list."""
    items: list[ExportJobResponse]
    total: int
    page: int
    limit: int
    pages: int


# ============== Scheduled Export Schemas ==============

class ScheduledExportCreate(BaseModel):
    """Create a scheduled export."""
    name: str = Field(..., min_length=1, max_length=256)
    template_id: str
    cron_expression: str = Field(..., max_length=100)
    timezone: str = Field(default="UTC", max_length=50)
    delivery_config: DeliveryConfig
    is_active: bool = True


class ScheduledExportUpdate(BaseModel):
    """Update a scheduled export."""
    name: str | None = Field(None, min_length=1, max_length=256)
    cron_expression: str | None = Field(None, max_length=100)
    timezone: str | None = Field(None, max_length=50)
    delivery_config: DeliveryConfig | None = None
    is_active: bool | None = None


class ScheduledExportResponse(BaseModel):
    """Scheduled export response."""
    id: str
    organization_id: str
    template_id: str
    name: str
    cron_expression: str
    timezone: str
    delivery_config: dict[str, Any]
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Available Columns Schema ==============

class AvailableColumnsResponse(BaseModel):
    """Available columns for a data type."""
    data_type: ExportDataType
    columns: list[ExportColumn]


# ============== Download Schema ==============

class ExportDownloadResponse(BaseModel):
    """Export download URL response."""
    download_url: str
    expires_in_seconds: int
    filename: str
    file_size_bytes: int | None
    # SEC-14: Signed token for direct file download
    download_token: str | None = None


# ============== Preview Schema ==============

class ExportPreviewRequest(BaseModel):
    """Request export data preview."""
    data_type: ExportDataType
    columns: list[str]
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)


class ExportPreviewResponse(BaseModel):
    """Export data preview response."""
    columns: list[str]
    rows: list[dict[str, Any]]
    total_count: int
