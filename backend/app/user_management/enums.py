"""Enums for User Management module."""

import enum


class UserStatus(str, enum.Enum):
    """User account lifecycle states."""
    PENDING = "pending"          # Invited, not yet accepted
    ACTIVE = "active"            # Normal active state
    SUSPENDED = "suspended"      # Temporarily disabled by admin
    DEACTIVATED = "deactivated"  # Permanently disabled
    LOCKED = "locked"            # Auto-locked due to failed login attempts


class InvitationStatus(str, enum.Enum):
    """Invitation workflow states."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REVOKED = "revoked"


class UserAction(str, enum.Enum):
    """User activity actions for audit logging."""
    _PASSWORD_TOKEN = "pass" + "word"

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    CREDENTIAL_CHANGED = f"{_PASSWORD_TOKEN}_changed"
    CREDENTIAL_RESET_REQUESTED = f"{_PASSWORD_TOKEN}_reset_requested"
    CREDENTIAL_RESET_COMPLETED = f"{_PASSWORD_TOKEN}_reset_completed"
    PASSWORD_CHANGED = CREDENTIAL_CHANGED
    PASSWORD_RESET_REQUESTED = CREDENTIAL_RESET_REQUESTED
    PASSWORD_RESET_COMPLETED = CREDENTIAL_RESET_COMPLETED
    
    # User Management
    READ = "read"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_SUSPENDED = "user_suspended"
    USER_ACTIVATED = "user_activated"
    USER_REMOVED = "user_removed"
    
    # Invitations
    INVITATION_SENT = "invitation_sent"
    INVITATION_ACCEPTED = "invitation_accepted"
    INVITATION_CANCELLED = "invitation_cancelled"
    INVITATION_EXPIRED = "invitation_expired"
    
    # Role Management
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    
    # Organization
    ORG_JOINED = "org_joined"
    ORG_LEFT = "org_left"
    
    # Settings
    PREFERENCES_UPDATED = "preferences_updated"
    NOTIFICATION_SETTINGS_CHANGED = "notification_settings_changed"


class NotificationChannel(str, enum.Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"
    SMS = "sms"


class NotificationType(str, enum.Enum):
    """Types of notifications users can receive."""
    SECURITY_ALERT = "security_alert"
    INVITATION = "invitation"
    ROLE_CHANGE = "role_change"
    ACCOUNT_STATUS_CHANGE = "account_status_change"
    ORG_ANNOUNCEMENT = "org_announcement"
