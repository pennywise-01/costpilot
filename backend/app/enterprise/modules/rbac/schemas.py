from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.enums import (
    PermissionAction,
    RBACResourceType,
    ABACOperator,
    AccessReviewStatus,
)
from app.shared.pagination import PaginatedResponse


# ---- Permission schemas ----

class PermissionEntry(BaseModel):
    action: PermissionAction
    resource_type: RBACResourceType


class PermissionResponse(PermissionEntry):
    id: str
    model_config = {"from_attributes": True}


# ---- Role schemas ----

class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    permissions: list[PermissionEntry] = Field(default_factory=list)
    is_default: bool = False


class RoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    permissions: list[PermissionEntry] | None = None
    is_default: bool | None = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    organization_id: str
    is_default: bool
    permissions: list[PermissionResponse]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PaginatedRoles(PaginatedResponse[RoleResponse]):
    """Paginated response for roles list."""
    pass


# ---- User-role assignment schemas ----

class UserRoleAssign(BaseModel):
    user_id: str
    role_id: str


class UserRoleResponse(BaseModel):
    id: str
    user_id: str
    role_id: str
    organization_id: str
    role: RoleResponse
    created_at: datetime
    model_config = {"from_attributes": True}


class PaginatedUserRoles(PaginatedResponse[UserRoleResponse]):
    """Paginated response for user role assignments list."""
    pass


# ---- ABAC policy schemas ----

class ABACPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    resource_type: RBACResourceType
    action: PermissionAction
    attribute_key: str = Field(min_length=1, max_length=256)
    operator: ABACOperator
    attribute_value: str
    effect_allow: bool = True
    active: bool = True


class ABACPolicyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = None
    resource_type: RBACResourceType | None = None
    action: PermissionAction | None = None
    attribute_key: str | None = Field(None, min_length=1, max_length=256)
    operator: ABACOperator | None = None
    attribute_value: str | None = None
    effect_allow: bool | None = None
    active: bool | None = None


class ABACPolicyResponse(BaseModel):
    id: str
    name: str
    description: str
    organization_id: str
    resource_type: RBACResourceType
    action: PermissionAction
    attribute_key: str
    operator: ABACOperator
    attribute_value: str
    effect_allow: bool
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PaginatedABACPolicies(PaginatedResponse[ABACPolicyResponse]):
    """Paginated response for ABAC policies list."""
    pass


# ---- Access review schemas ----

class AccessReviewCreate(BaseModel):
    user_id: str
    role_id: str
    notes: str = ""


class AccessReviewDecision(BaseModel):
    status: AccessReviewStatus
    notes: str | None = None


class AccessReviewResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    reviewer_id: str
    role_id: str
    status: AccessReviewStatus
    notes: str
    role: RoleResponse
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ---- Permission check schemas ----

class PermissionCheckRequest(BaseModel):
    user_id: str
    action: PermissionAction
    resource_type: RBACResourceType
    resource_attributes: dict[str, str] = Field(default_factory=dict)


class PermissionCheckResponse(BaseModel):
    allowed: bool
    matched_roles: list[str]
    matched_policies: list[str]


# ---- Overview schema ----

# ---- SSO config schemas ----

class SSOConfigCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    issuer_url: str = Field(min_length=1, max_length=512)
    client_id: str = ""
    metadata_url: str = ""
    enabled: bool = False
    auto_provision_roles: bool = False
    default_role_id: str | None = None


class SSOConfigUpdate(BaseModel):
    issuer_url: str | None = Field(None, min_length=1, max_length=512)
    client_id: str | None = None
    metadata_url: str | None = None
    enabled: bool | None = None
    auto_provision_roles: bool | None = None
    default_role_id: str | None = None


class SSOConfigResponse(BaseModel):
    id: str
    organization_id: str
    provider: str
    issuer_url: str
    client_id: str
    metadata_url: str
    enabled: bool
    auto_provision_roles: bool
    default_role_id: str | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ---- Overview schema ----

class RBACOverview(BaseModel):
    total_roles: int
    total_assignments: int
    total_abac_policies: int
    pending_reviews: int
    sso_configs: list[SSOConfigResponse]
    roles: list[RoleResponse]
