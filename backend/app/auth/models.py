from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Integer, String, DateTime, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import RolePurpose, UserStatus


class SessionRevokeReason(str, PyEnum):
    """Reasons for session revocation."""
    MANUAL_LOGOUT = "manual_logout"
    MAX_CONCURRENT_SESSIONS = "max_concurrent_sessions"
    ADMIN_FORCE_LOGOUT = "admin_force_logout"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class SecurityEventType(str, PyEnum):
    """Types of security events that can be logged."""
    SESSION_VALIDATION_FAILED = "session_validation_failed"
    SESSION_BINDING_MISMATCH = "session_binding_mismatch"
    SUSPICIOUS_IP_CHANGE = "suspicious_ip_change"
    TOKEN_BLACKLISTED = "token_blacklisted"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    FORCE_LOGOUT = "force_logout"


class SecurityEvent(BaseModel):
    """Security audit log for tracking authentication and session events."""
    __tablename__ = "security_events"

    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[SecurityEventType] = mapped_column(
        SAEnum(SecurityEventType, name="securityeventtype"),
        nullable=False,
        index=True,
    )
    # Hashed IP address for privacy - never store raw IPs
    ip_address_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whether this was a successful or failed security check
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SessionBinding(BaseModel):
    """Server-side session tracking for concurrent session limits."""
    __tablename__ = "session_bindings"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    revoke_reason: Mapped[SessionRevokeReason | None] = mapped_column(
        SAEnum(SessionRevokeReason, name="sessionrevokereason"), nullable=True
    )


class User(BaseModel, OptimisticLockingMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[RolePurpose] = mapped_column(
        SAEnum(
            RolePurpose,
            name="rolepurpose",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=RolePurpose.MEMBER,
        nullable=False,
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # User management fields (added via migration 004)
    status: Mapped[UserStatus] = mapped_column(
        String(32), default=UserStatus.ACTIVE, nullable=False, index=True
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
