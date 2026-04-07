"""Data Export models for export jobs, templates, and scheduling."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.enterprise.modules.export.enums import ExportDataType, ExportFormat, ExportStatus


class ExportTemplate(BaseModel, OptimisticLockingMixin):
    """Reusable export configuration templates."""
    
    __tablename__ = "export_templates"
    
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[ExportDataType] = mapped_column(String(64), nullable=False, index=True)
    format: Mapped[ExportFormat] = mapped_column(String(32), nullable=False)
    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    date_range_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_by: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sort_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[str] = mapped_column(String(10), default="desc")
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class ExportJob(BaseModel, OptimisticLockingMixin):
    """Individual export job execution."""
    
    __tablename__ = "export_jobs"
    
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    template_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("export_templates.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    data_type: Mapped[ExportDataType] = mapped_column(String(64), nullable=False, index=True)
    format: Mapped[ExportFormat] = mapped_column(String(32), nullable=False)
    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    date_range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    group_by: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sort_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Execution status
    status: Mapped[ExportStatus] = mapped_column(
        String(32), default=ExportStatus.PENDING, nullable=False, index=True
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Scheduling
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    delivery_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    template: Mapped["ExportTemplate"] = relationship("ExportTemplate", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")


class ScheduledExport(BaseModel, OptimisticLockingMixin):
    """Recurring scheduled exports."""
    
    __tablename__ = "scheduled_exports"
    
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("export_templates.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    delivery_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    template: Mapped["ExportTemplate"] = relationship("ExportTemplate", lazy="selectin")
    creator: Mapped["User"] = relationship("User", lazy="selectin")
