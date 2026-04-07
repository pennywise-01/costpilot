"""Pydantic schemas for scheduler module."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.scheduler.enums import LogLevel, ScheduleType, SchedulerStatus, TriggerType


# ==================== SchedulerConfig Schemas ====================

class SchedulerConfigBase(BaseModel):
    """Base schema for scheduler config."""

    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None

    # Data types to collect
    collect_expenses: bool = True
    collect_resources: bool = True
    collect_recommendations: bool = True

    # Schedule configuration
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    interval_minutes: int | None = Field(None, ge=5, le=10080)  # 5 min to 1 week
    cron_expression: str | None = None

    # Timing options
    timezone: str = "UTC"
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Failure handling
    max_consecutive_failures: int = Field(3, ge=1, le=10)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str | None, info: Any) -> str | None:
        """Validate cron expression when schedule_type is cron."""
        values = info.data
        if values.get("schedule_type") == ScheduleType.CRON and not v:
            raise ValueError("Cron expression is required when schedule_type is 'cron'")
        if values.get("schedule_type") != ScheduleType.CRON and v:
            # Clear cron if not using cron schedule
            return None
        return v

    @field_validator("interval_minutes")
    @classmethod
    def validate_interval_minutes(cls, v: int | None, info: Any) -> int | None:
        """Validate interval minutes when schedule_type is interval."""
        values = info.data
        if values.get("schedule_type") == ScheduleType.INTERVAL and not v:
            raise ValueError(
                "Interval minutes is required when schedule_type is 'interval'"
            )
        if values.get("schedule_type") != ScheduleType.INTERVAL and v:
            # Clear interval if not using interval schedule
            return None
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: datetime | None, info: Any) -> datetime | None:
        """Validate end_date is after start_date."""
        values = info.data
        if v and values.get("start_date") and v <= values["start_date"]:
            raise ValueError("End date must be after start date")
        return v


class SchedulerConfigCreate(SchedulerConfigBase):
    """Schema for creating a scheduler config."""

    is_enabled: bool = True


class SchedulerConfigUpdate(BaseModel):
    """Schema for updating a scheduler config."""

    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = None
    collect_expenses: bool | None = None
    collect_resources: bool | None = None
    collect_recommendations: bool | None = None
    schedule_type: ScheduleType | None = None
    interval_minutes: int | None = Field(None, ge=5, le=10080)
    cron_expression: str | None = None
    timezone: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_enabled: bool | None = None
    max_consecutive_failures: int | None = Field(None, ge=1, le=10)

    model_config = ConfigDict(from_attributes=True)


class SchedulerConfigResponse(SchedulerConfigBase):
    """Schema for scheduler config response."""

    id: str
    organization_id: str
    is_enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime
    created_by: str

    model_config = ConfigDict(from_attributes=True)


class SchedulerConfigListResponse(BaseModel):
    """Schema for list of scheduler configs."""

    items: list[SchedulerConfigResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)


# ==================== SchedulerRun Schemas ====================

class SchedulerRunBase(BaseModel):
    """Base schema for scheduler run."""

    started_at: datetime
    completed_at: datetime | None
    duration_seconds: int | None
    status: SchedulerStatus

    # What was collected
    collected_expenses: bool
    collected_resources: bool
    collected_recommendations: bool

    # Status per data type
    expenses_status: str | None
    resources_status: str | None
    recommendations_status: str | None

    # Record counts
    expenses_records: int
    resources_records: int
    recommendations_records: int

    # Error information
    error_message: str | None
    error_details: dict[str, Any] | None

    # Trigger information
    trigger_type: TriggerType
    triggered_by: str | None

    model_config = ConfigDict(from_attributes=True)


class SchedulerRunResponse(SchedulerRunBase):
    """Schema for scheduler run response."""

    id: str
    scheduler_config_id: str
    organization_id: str

    model_config = ConfigDict(from_attributes=True)


class SchedulerRunListResponse(BaseModel):
    """Schema for list of scheduler runs."""

    items: list[SchedulerRunResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# ==================== SchedulerLog Schemas ====================

class SchedulerLogBase(BaseModel):
    """Base schema for scheduler log."""

    logged_at: datetime
    level: LogLevel
    message: str
    data_type: str | None
    cloud_account_id: str | None
    cloud_account_name: str | None
    details: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class SchedulerLogResponse(SchedulerLogBase):
    """Schema for scheduler log response."""

    id: str
    scheduler_run_id: str

    model_config = ConfigDict(from_attributes=True)


class SchedulerLogListResponse(BaseModel):
    """Schema for list of scheduler logs."""

    items: list[SchedulerLogResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


# ==================== Statistics & Dashboard Schemas ====================

class SchedulerStats(BaseModel):
    """Statistics for a scheduler."""

    total_runs: int
    successful_runs: int
    failed_runs: int
    partial_runs: int
    avg_duration_seconds: float | None
    last_run_status: str | None
    last_run_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SchedulerStatsResponse(BaseModel):
    """Schema for scheduler statistics response."""

    scheduler_id: str
    stats: SchedulerStats

    model_config = ConfigDict(from_attributes=True)


class OrganizationSchedulerStats(BaseModel):
    """Overall scheduler statistics for an organization."""

    total_schedulers: int
    active_schedulers: int
    inactive_schedulers: int
    total_runs_today: int
    successful_runs_today: int
    failed_runs_today: int
    upcoming_runs: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


# ==================== Trigger & Control Schemas ====================

class ManualTriggerRequest(BaseModel):
    """Request to manually trigger a scheduler."""

    collect_expenses: bool | None = None  # Override config if provided
    collect_resources: bool | None = None
    collect_recommendations: bool | None = None


class ManualTriggerResponse(BaseModel):
    """Response from manual trigger."""

    success: bool
    run_id: str | None
    message: str

    model_config = ConfigDict(from_attributes=True)


class ToggleSchedulerRequest(BaseModel):
    """Request to toggle scheduler enabled state."""

    is_enabled: bool


class ToggleSchedulerResponse(BaseModel):
    """Response from toggle operation."""

    success: bool
    is_enabled: bool
    message: str

    model_config = ConfigDict(from_attributes=True)


# ==================== Dead Letter Job Schemas ====================

class DeadLetterJobResponse(BaseModel):
    """Schema for dead letter job response."""

    id: str
    scheduler_config_id: str
    original_run_id: str | None
    error_message: str
    error_traceback: str | None
    failure_count: int
    max_retries: int
    status: str  # pending, retried, abandoned
    scheduled_retry_at: datetime | None
    last_retried_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeadLetterJobListResponse(BaseModel):
    """Schema for list of dead letter jobs."""

    items: list[DeadLetterJobResponse]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)


class RetryDeadLetterJobResponse(BaseModel):
    """Response from retrying a dead letter job."""

    success: bool
    run_id: str | None
    message: str

    model_config = ConfigDict(from_attributes=True)
