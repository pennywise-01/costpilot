"""Database models for scheduler module."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.shared.models import OptimisticLockingMixin


class SchedulerConfig(Base, OptimisticLockingMixin):
    """Configuration for scheduled data collection jobs."""

    __tablename__ = "scheduler_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Data types to collect
    collect_expenses: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    collect_resources: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    collect_recommendations: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Schedule configuration
    schedule_type: Mapped[str] = mapped_column(
        String(20), default="interval", nullable=False
    )  # interval, cron, once
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timing options
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Failure tracking
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_consecutive_failures: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    organization = relationship("Organization", back_populates="scheduler_configs")
    runs: Mapped[list["SchedulerRun"]] = relationship(
        "SchedulerRun", back_populates="scheduler_config", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SchedulerConfig(id={self.id}, name={self.name}, enabled={self.is_enabled})>"


class SchedulerRun(Base):
    """Record of a scheduler execution."""

    __tablename__ = "scheduler_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheduler_config_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scheduler_configs.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Execution timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Status: pending, running, completed, failed, cancelled, partial
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # What was collected
    collected_expenses: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    collected_resources: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    collected_recommendations: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Results per data type
    expenses_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resources_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recommendations_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Record counts
    expenses_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resources_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommendations_records: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    # Error information
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Trigger information
    trigger_type: Mapped[str] = mapped_column(
        String(20), default="scheduled", nullable=False
    )  # scheduled, manual, api
    triggered_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    scheduler_config = relationship("SchedulerConfig", back_populates="runs")
    logs: Mapped[list["SchedulerLog"]] = relationship(
        "SchedulerLog", back_populates="scheduler_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SchedulerRun(id={self.id}, status={self.status}, started_at={self.started_at})>"


class SchedulerLog(Base):
    """Detailed logs for scheduler runs."""

    __tablename__ = "scheduler_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheduler_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scheduler_runs.id"), nullable=False, index=True
    )

    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # debug, info, warning, error
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Additional context
    data_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # expenses, resources, recommendations
    cloud_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cloud_account_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    scheduler_run = relationship("SchedulerRun", back_populates="logs")

    def __repr__(self) -> str:
        return f"<SchedulerLog(id={self.id}, level={self.level}, data_type={self.data_type})>"


class DeadLetterJob(Base, OptimisticLockingMixin):
    """Dead letter queue for failed scheduler jobs that exceeded max retries."""

    __tablename__ = "dead_letter_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scheduler_config_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    original_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=1)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, retried, abandoned
    scheduled_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_retried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DeadLetterJob(id={self.id}, scheduler_config_id={self.scheduler_config_id}, status={self.status})>"
