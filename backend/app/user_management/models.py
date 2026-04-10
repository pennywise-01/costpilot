"""User Management models for user lifecycle and access control."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import UserStatus
from app.shared.utils.time import utc_now
from app.user_management.enums import InvitationStatus, UserAction


class UserInvitation(BaseModel, OptimisticLockingMixin):
    """Track pending user invitations to organizations."""
    
    __tablename__ = "user_invitations"
    
    email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    invited_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    role_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rbac_roles.id"), nullable=True
    )
    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    status: Mapped[InvitationStatus] = mapped_column(
        String(32), default=InvitationStatus.PENDING, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", lazy="selectin"
    )
    inviter: Mapped["User"] = relationship(
        "User", foreign_keys=[invited_by], lazy="selectin"
    )
    role: Mapped["Role"] = relationship(
        "Role", lazy="selectin"
    )
    
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        expires = self.expires_at
        # Ensure both datetimes are timezone-aware
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return utc_now() > expires

    def is_valid(self) -> bool:
        """Check if invitation is still valid (pending and not expired)."""
        return self.status == InvitationStatus.PENDING and not self.is_expired()


class UserActivityLog(BaseModel):
    """Audit trail for user actions within organizations."""
    
    __tablename__ = "user_activity_logs"
    
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    action: Mapped[UserAction] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", lazy="selectin")
    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")


class UserPreferences(BaseModel, OptimisticLockingMixin):
    """User-specific preferences and settings."""
    
    __tablename__ = "user_preferences"
    
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    notification_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    dashboard_layout: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", lazy="selectin")
