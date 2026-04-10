"""Database models for cost cache.

Stores aggregated cost data for fast dashboard retrieval without
blocking on CSP API calls.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DECIMAL,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.shared.utils.time import utc_now


def generate_uuid() -> str:
    return str(uuid.uuid4())


class CostCache(Base):
    """Stores aggregated cost data for fast dashboard retrieval."""

    __tablename__ = "cost_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    cloud_account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cloud_accounts.id"), nullable=True, index=True
    )

    # Data type: 'summary', 'breakdown', 'daily', 'forecast'
    cache_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Time period this data covers
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Cost values (all in USD)
    this_month_total: Mapped[float] = mapped_column(
        DECIMAL(15, 2), default=0, nullable=False
    )
    last_month_total: Mapped[float] = mapped_column(
        DECIMAL(15, 2), default=0, nullable=False
    )
    forecast_total: Mapped[float] = mapped_column(
        DECIMAL(15, 2), default=0, nullable=False
    )
    change_percent: Mapped[float] = mapped_column(
        DECIMAL(5, 2), default=0, nullable=False
    )

    # For breakdown data (stored as JSON)
    breakdown_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    # Metadata
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # Cache status: 'live', 'cache', 'stale', 'error'
    data_source: Mapped[str] = mapped_column(
        String(20), default="live", nullable=False
    )

    # Timestamps
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization = relationship("Organization", back_populates="cost_caches")
    cloud_account = relationship("CloudAccount", back_populates="cost_caches")

    # Unique constraint for lookups
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "cache_type",
            "cloud_account_id",
            "period_start",
            "period_end",
            name="uix_cost_cache_lookup",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CostCache("
            f"org={self.organization_id[:8]}..., "
            f"type={self.cache_type}, "
            f"this_month=${self.this_month_total}, "
            f"expires={self.expires_at.isoformat()}"
            f")>"
        )

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return utc_now() > self.expires_at

    def age_hours(self) -> float:
        """Get age of this cache entry in hours."""
        delta = utc_now() - self.collected_at
        return delta.total_seconds() / 3600


class CostCacheStatus(Base):
    """Tracks the overall cache health per organization."""

    __tablename__ = "cost_cache_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True
    )

    # Last successful collection
    last_successful_collection: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 'pending', 'success', 'partial', 'failed'
    last_collection_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    # What was collected
    accounts_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accounts_success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accounts_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Error info (if failed)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Next scheduled collection
    next_collection_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization = relationship("Organization", back_populates="cost_cache_status")

    def __repr__(self) -> str:
        return (
            f"<CostCacheStatus("
            f"org={self.organization_id[:8]}..., "
            f"status={self.last_collection_status}, "
            f"success={self.accounts_success}/{self.accounts_total}"
            f")>"
        )

    def is_healthy(self) -> bool:
        """Check if cache is healthy (recent successful collection)."""
        if not self.last_successful_collection:
            return False
        # Ensure both datetimes are timezone-aware
        last_time = self.last_successful_collection
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        hours_since = (utc_now() - last_time).total_seconds() / 3600
        return hours_since < 24  # Consider healthy if updated within 24 hours

    def get_health_status(self) -> str:
        """Get detailed health status."""
        if not self.last_successful_collection:
            return "uninitialized"

        # Ensure both datetimes are timezone-aware
        last_time = self.last_successful_collection
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        hours_since = (utc_now() - last_time).total_seconds() / 3600

        if hours_since < 6:
            return "healthy"
        elif hours_since < 24:
            return "stale"
        else:
            return "expired"