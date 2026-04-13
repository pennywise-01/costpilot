"""Pydantic schemas for User Management module."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.shared.enums import PermissionAction, RBACResourceType, UserStatus
from app.user_management.enums import InvitationStatus, UserAction


# ============== Pagination Schemas ==============

class PaginationParams(BaseModel):
    """Common pagination parameters."""
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at")
    sort_order: Literal["asc", "desc"] = Field(default="desc")


class PaginatedResult(BaseModel):
    """Generic paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    limit: int
    pages: int


# ============== Role Summary Schemas ==============

class RoleSummary(BaseModel):
    """Simplified role information for user listings."""
    id: str
    name: str
    description: str

    model_config = ConfigDict(from_attributes=True)


# ============== Permission Schemas ==============

class PermissionEntry(BaseModel):
    """Individual permission entry."""
    action: PermissionAction
    resource_type: RBACResourceType


class UserPermissionResponse(BaseModel):
    """User's effective permissions response."""
    action: PermissionAction
    resource_type: RBACResourceType
    granted_via_role: str | None = None
    granted_via_abac: bool = False


# ============== User List/Detail Schemas ==============

class UserListItem(BaseModel):
    """User item for list views."""
    id: str
    email: str
    display_name: str
    status: UserStatus
    is_active: bool
    last_login: datetime | None
    roles: list[RoleSummary]
    department: str | None
    job_title: str | None
    joined_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserActivitySummary(BaseModel):
    """Summary of user activity."""
    last_login: datetime | None
    login_count_30d: int
    actions_count_30d: int


class UserDetail(UserListItem):
    """Detailed user information."""
    preferences: dict[str, Any] | None
    activity_summary: UserActivitySummary
    permissions: list[UserPermissionResponse]
    invited_by: dict[str, str] | None = None  # id, display_name


# ============== User Update Schemas ==============

class UserUpdateRequest(BaseModel):
    """Request to update user details."""
    display_name: str | None = Field(None, min_length=1, max_length=256)
    department: str | None = Field(None, max_length=128)
    job_title: str | None = Field(None, max_length=128)
    is_active: bool | None = None


class UserStatusUpdateRequest(BaseModel):
    """Request to change user status."""
    status: UserStatus
    reason: str | None = Field(None, max_length=500)


class AdminResetPasswordRequest(BaseModel):
    """Request for admin to reset a user's password."""
    new_password: str = Field(min_length=8, max_length=128)


# ============== Invitation Schemas ==============

class UserInviteRequest(BaseModel):
    """Request to invite a single user."""
    email: EmailStr
    role_id: str
    department: str | None = Field(None, max_length=128)
    job_title: str | None = Field(None, max_length=128)
    message: str | None = Field(None, max_length=1000)


class UserInviteBulkRequest(BaseModel):
    """Request to invite multiple users."""
    invitations: list[UserInviteRequest] = Field(..., min_length=1, max_length=50)


class UserInviteResponse(BaseModel):
    """Response for invitation creation."""
    id: str
    email: str
    invitation_token: str  # Token used in acceptance URL
    status: str  # "sent" or "failed"
    error: str | None = None
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkInviteResponse(BaseModel):
    """Response for bulk invitation."""
    total: int
    successful: int
    failed: int
    results: list[UserInviteResponse]


class InvitationAcceptRequest(BaseModel):
    """Request to accept an invitation."""
    display_name: str = Field(..., min_length=1, max_length=256)
    password: str = Field(..., min_length=8, max_length=128)


class InvitationDetail(BaseModel):
    """Invitation details for acceptance page."""
    token: str
    email: str
    organization_name: str
    invited_by_name: str
    role_name: str | None
    expires_at: datetime
    is_valid: bool

    model_config = ConfigDict(from_attributes=True)


# ============== Role Assignment Schemas ==============

class UserRoleUpdateRequest(BaseModel):
    """Request to update user roles."""
    role_ids: list[str]
    action: Literal["assign", "revoke", "replace"] = "replace"
    reason: str | None = Field(None, max_length=500)
    expires_at: datetime | None = None  # For temporary access


class UserRoleAssignmentResponse(BaseModel):
    """User role assignment response."""
    id: str
    user_id: str
    role_id: str
    role: RoleSummary
    organization_id: str
    assigned_by: str | None
    assigned_at: datetime
    expires_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ============== Activity Log Schemas ==============

class ActivityLogEntry(BaseModel):
    """Single activity log entry."""
    id: str
    user_id: str
    action: UserAction
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    action_metadata: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityLogListResponse(PaginatedResult):
    """Paginated activity log response."""
    items: list[ActivityLogEntry]


class ActivityLogFilter(BaseModel):
    """Filters for activity log queries."""
    action: UserAction | None = None
    resource_type: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


# ============== Effective Permissions Schema ==============

class EffectivePermissionsResponse(BaseModel):
    """Response with user's effective permissions."""
    user_id: str
    organization_id: str
    roles: list[RoleSummary]
    permissions: list[UserPermissionResponse]
    abac_policies: list[dict[str, Any]]
    calculated_at: datetime


# ============== User Preferences Schemas ==============

class UserPreferencesUpdate(BaseModel):
    """Request to update user preferences."""
    timezone: str | None = Field(None, max_length=64)
    language: str | None = Field(None, max_length=10)
    notification_settings: dict[str, Any] | None = None
    dashboard_layout: dict[str, Any] | None = None


class UserPreferencesResponse(BaseModel):
    """User preferences response."""
    user_id: str
    timezone: str
    language: str
    notification_settings: dict[str, Any]
    dashboard_layout: dict[str, Any] | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Filter Schemas ==============

class UserListFilters(BaseModel):
    """Filters for user list queries."""
    status: UserStatus | None = None
    role_id: str | None = None
    department: str | None = None
    search: str | None = Field(None, max_length=100)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at")
    sort_order: Literal["asc", "desc"] = Field(default="desc")
