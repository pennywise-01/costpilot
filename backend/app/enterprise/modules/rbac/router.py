from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.organizations.models import Employee
from app.shared.enums import AccessReviewStatus, PermissionAction, RBACResourceType
from app.shared.exceptions import ForbiddenError
from app.enterprise.modules.rbac.schemas import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    UserRoleAssign,
    UserRoleResponse,
    ABACPolicyCreate,
    ABACPolicyUpdate,
    ABACPolicyResponse,
    AccessReviewCreate,
    AccessReviewDecision,
    AccessReviewResponse,
    PermissionCheckRequest,
    PermissionCheckResponse,
    SSOConfigCreate,
    SSOConfigUpdate,
    SSOConfigResponse,
    RBACOverview,
    PaginatedRoles,
    PaginatedUserRoles,
    PaginatedABACPolicies,
)
from app.enterprise.modules.rbac.service import (
    create_role,
    list_roles,
    get_role,
    update_role,
    delete_role,
    assign_role,
    list_user_roles,
    revoke_role,
    create_abac_policy,
    list_abac_policies,
    update_abac_policy,
    delete_abac_policy,
    create_access_review,
    list_access_reviews,
    decide_access_review,
    check_permission,
    get_rbac_overview,
    create_sso_config,
    list_sso_configs,
    update_sso_config,
    delete_sso_config,
)
from app.shared.org_access import get_current_org_member
from app.shared.pagination import PaginatedResponse

router = APIRouter()


async def _require_rbac_view(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    """Allow only users who can at least read user data in this organization."""
    result = await check_permission(
        db,
        org_id,
        PermissionCheckRequest(
            user_id=member.auth_user_id,
            action=PermissionAction.READ,
            resource_type=RBACResourceType.USER,
        ),
    )
    if not result.allowed:
        raise ForbiddenError("You don't have permission to view RBAC settings")
    return member


async def _require_rbac_admin(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    """Allow only users who can manage users in this organization."""
    result = await check_permission(
        db,
        org_id,
        PermissionCheckRequest(
            user_id=member.auth_user_id,
            action=PermissionAction.MANAGE,
            resource_type=RBACResourceType.USER,
        ),
    )
    if not result.allowed:
        raise ForbiddenError("You don't have permission to manage RBAC settings")
    return member


# ──────────────────── Overview ────────────────────

@router.get("/{org_id}/rbac", response_model=RBACOverview)
async def rbac_overview(
    org_id: str,
    member: Employee = Depends(_require_rbac_view),
    db: AsyncSession = Depends(get_db),
):
    data = await get_rbac_overview(db, org_id)
    return RBACOverview.model_validate(data)


# ──────────────────── Roles ────────────────────

@router.post("/{org_id}/rbac/roles", response_model=RoleResponse, status_code=201)
async def create_role_endpoint(
    org_id: str,
    data: RoleCreate,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    role = await create_role(db, org_id, data)
    return RoleResponse.model_validate(role)


@router.get("/{org_id}/rbac/roles", response_model=PaginatedRoles)
async def list_roles_endpoint(
    org_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    member: Employee = Depends(_require_rbac_view),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    roles, total = await list_roles(db, org_id, offset=offset, limit=page_size)
    return PaginatedResponse.create(
        items=[RoleResponse.model_validate(r) for r in roles],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{org_id}/rbac/roles/{role_id}", response_model=RoleResponse)
async def get_role_endpoint(
    org_id: str,
    role_id: str,
    member: Employee = Depends(_require_rbac_view),
    db: AsyncSession = Depends(get_db),
):
    role = await get_role(db, org_id, role_id)
    return RoleResponse.model_validate(role)


@router.patch("/{org_id}/rbac/roles/{role_id}", response_model=RoleResponse)
async def update_role_endpoint(
    org_id: str,
    role_id: str,
    data: RoleUpdate,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    role = await update_role(db, org_id, role_id, data)
    return RoleResponse.model_validate(role)


@router.delete("/{org_id}/rbac/roles/{role_id}", response_model=RoleResponse)
async def delete_role_endpoint(
    org_id: str,
    role_id: str,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    role = await delete_role(db, org_id, role_id)
    return RoleResponse.model_validate(role)


# ──────────────────── User-Role Assignments ────────────────────

@router.post("/{org_id}/rbac/assignments", response_model=UserRoleResponse, status_code=201)
async def assign_role_endpoint(
    org_id: str,
    data: UserRoleAssign,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    assignment = await assign_role(db, org_id, data.user_id, data.role_id)
    return UserRoleResponse.model_validate(assignment)


@router.get("/{org_id}/rbac/assignments", response_model=PaginatedUserRoles)
async def list_assignments_endpoint(
    org_id: str,
    user_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    member: Employee = Depends(_require_rbac_view),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    assignments, total = await list_user_roles(db, org_id, user_id=user_id, offset=offset, limit=page_size)
    return PaginatedResponse.create(
        items=[UserRoleResponse.model_validate(a) for a in assignments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/{org_id}/rbac/assignments/{assignment_id}", response_model=UserRoleResponse)
async def revoke_role_endpoint(
    org_id: str,
    assignment_id: str,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    assignment = await revoke_role(db, org_id, assignment_id)
    return UserRoleResponse.model_validate(assignment)


# ──────────────────── ABAC Policies ────────────────────

@router.post("/{org_id}/rbac/policies", response_model=ABACPolicyResponse, status_code=201)
async def create_policy_endpoint(
    org_id: str,
    data: ABACPolicyCreate,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    policy = await create_abac_policy(db, org_id, data)
    return ABACPolicyResponse.model_validate(policy)


@router.get("/{org_id}/rbac/policies", response_model=PaginatedABACPolicies)
async def list_policies_endpoint(
    org_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    member: Employee = Depends(_require_rbac_view),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    policies, total = await list_abac_policies(db, org_id, offset=offset, limit=page_size)
    return PaginatedResponse.create(
        items=[ABACPolicyResponse.model_validate(p) for p in policies],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{org_id}/rbac/policies/{policy_id}", response_model=ABACPolicyResponse)
async def update_policy_endpoint(
    org_id: str,
    policy_id: str,
    data: ABACPolicyUpdate,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    policy = await update_abac_policy(db, org_id, policy_id, data)
    return ABACPolicyResponse.model_validate(policy)


@router.delete("/{org_id}/rbac/policies/{policy_id}", response_model=ABACPolicyResponse)
async def delete_policy_endpoint(
    org_id: str,
    policy_id: str,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    policy = await delete_abac_policy(db, org_id, policy_id)
    return ABACPolicyResponse.model_validate(policy)


# ──────────────────── Access Reviews ────────────────────

@router.post("/{org_id}/rbac/reviews", response_model=AccessReviewResponse, status_code=201)
async def create_review_endpoint(
    org_id: str,
    data: AccessReviewCreate,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    review = await create_access_review(db, org_id, member.auth_user_id, data)
    return AccessReviewResponse.model_validate(review)


@router.get("/{org_id}/rbac/reviews", response_model=list[AccessReviewResponse])
async def list_reviews_endpoint(
    org_id: str,
    status: AccessReviewStatus | None = Query(None),
    member: Employee = Depends(_require_rbac_view),
    db: AsyncSession = Depends(get_db),
):
    reviews = await list_access_reviews(db, org_id, status=status)
    return [AccessReviewResponse.model_validate(r) for r in reviews]


@router.patch("/{org_id}/rbac/reviews/{review_id}", response_model=AccessReviewResponse)
async def decide_review_endpoint(
    org_id: str,
    review_id: str,
    data: AccessReviewDecision,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    review = await decide_access_review(db, org_id, review_id, data)
    return AccessReviewResponse.model_validate(review)


# ──────────────────── Permission Check ────────────────────

@router.post("/{org_id}/rbac/check", response_model=PermissionCheckResponse)
async def check_permission_endpoint(
    org_id: str,
    data: PermissionCheckRequest,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await check_permission(db, org_id, data)
    return result


# ──────────────────── SSO Configs ────────────────────

@router.post("/{org_id}/rbac/sso", response_model=SSOConfigResponse, status_code=201)
async def create_sso_endpoint(
    org_id: str,
    data: SSOConfigCreate,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await create_sso_config(db, org_id, data)
    return SSOConfigResponse.model_validate(config)


@router.get("/{org_id}/rbac/sso", response_model=list[SSOConfigResponse])
async def list_sso_endpoint(
    org_id: str,
    member: Employee = Depends(_require_rbac_view),
    db: AsyncSession = Depends(get_db),
):
    configs = await list_sso_configs(db, org_id)
    return [SSOConfigResponse.model_validate(c) for c in configs]


@router.patch("/{org_id}/rbac/sso/{config_id}", response_model=SSOConfigResponse)
async def update_sso_endpoint(
    org_id: str,
    config_id: str,
    data: SSOConfigUpdate,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await update_sso_config(db, org_id, config_id, data)
    return SSOConfigResponse.model_validate(config)


@router.delete("/{org_id}/rbac/sso/{config_id}", response_model=SSOConfigResponse)
async def delete_sso_endpoint(
    org_id: str,
    config_id: str,
    member: Employee = Depends(_require_rbac_admin),
    db: AsyncSession = Depends(get_db),
):
    config = await delete_sso_config(db, org_id, config_id)
    return SSOConfigResponse.model_validate(config)
