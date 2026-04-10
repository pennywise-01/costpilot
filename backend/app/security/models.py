"""Models for security audit logging."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Audit log entry for security events."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="info"
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True
    )
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True
    )
    action_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    ip_address_hash: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True
    )
    user_agent_hash: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    # Indexes for common query patterns
    __table_args__ = (
        Index("idx_audit_logs_timestamp_type", "timestamp", "event_type"),
        Index("idx_audit_logs_org_event", "organization_id", "event_type"),
        Index("idx_audit_logs_user_event", "user_id", "event_type"),
        Index("idx_audit_logs_severity", "severity", "timestamp"),
    )


class SecurityAlert(Base):
    """Real-time security events for alerting."""
    
    __tablename__ = "security_alerts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
