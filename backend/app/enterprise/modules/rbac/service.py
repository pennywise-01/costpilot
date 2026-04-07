from datetime import datetime

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enterprise.modules.rbac.models import (
    Role,
    RolePermission,
    UserRoleAssignment,
    ABACPolicy,
    AccessReview,
    SSOConfig,
)
from app.enterprise.modules.rbac.schemas import (
    RoleCreate,
    RoleUpdate,
    ABACPolicyCreate,
    ABACPolicyUpdate,
    AccessReviewCreate,
    AccessReviewDecision,
    PermissionCheckRequest,
    PermissionCheckResponse,
    SSOConfigCreate,
    SSOConfigUpdate,
)
from app.shared.enums import ABACOperator, AccessReviewStatus, PermissionAction, RBACResourceType
from app.shared.exceptions import NotFoundError, ConflictError, BadRequestError, ForbiddenError
from app.shared.utils.time import utc_now


# ──────────────────── Roles ────────────────────

def _sync_role_permissions(
    role: Role,
    desired_permissions: set[tuple[PermissionAction, RBACResourceType]],
) -> None:
    """Synchronize permissions for a role without violating uniqueness constraints."""
    now = utc_now()
    existing_by_key = {
        (permission.action, permission.resource_type): permission
        for permission in role.permissions
    }

    for key, permission in existing_by_key.items():
        if key in desired_permissions:
            if permission.deleted_at is not None:
                permission.deleted_at = None
            continue

        if permission.deleted_at is None:
            permission.deleted_at = now

    for action, resource_type in desired_permissions:
        if (action, resource_type) in existing_by_key:
            continue
        role.permissions.append(
            RolePermission(
                role_id=role.id,
                action=action,
                resource_type=resource_type,
            )
        )

async def create_role(db: AsyncSession, org_id: str, data: RoleCreate) -> Role:
    from app.enterprise.modules.rbac.constants import SYSTEM_ROLE_NAMES

    if data.is_default:
        raise BadRequestError("Custom roles cannot be marked as default")

    normalized_system_names = {name.lower() for name in SYSTEM_ROLE_NAMES}
    if data.name.strip().lower() in normalized_system_names:
        raise BadRequestError("Role name is reserved for system roles")

    existing = await db.execute(
        select(Role).where(
            Role.organization_id == org_id,
            Role.name == data.name,
            Role.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Role '{data.name}' already exists")

    role = Role(
        name=data.name,
        description=data.description,
        organization_id=org_id,
        is_default=False,
    )
    db.add(role)
    await db.flush()

    for perm in data.permissions:
        db.add(RolePermission(
            role_id=role.id,
            action=perm.action,
            resource_type=perm.resource_type,
        ))

    await db.flush()
    await db.refresh(role)
    return role


async def seed_default_roles(db: AsyncSession, org_id: str) -> list[Role]:
    """Create default roles for a new organization.
    
    This should be called when a new organization is created.
    Returns the list of created roles.
    """
    from app.enterprise.modules.rbac.constants import DEFAULT_ROLES
    
    created_roles = []
    
    for role_config in DEFAULT_ROLES:
        desired_permissions = {
            (permission["action"], permission["resource_type"])
            for permission in role_config["permissions"]
        }

        # Check if role already exists
        existing = await db.execute(
            select(Role).where(
                Role.organization_id == org_id,
                Role.name == role_config["name"],
                Role.deleted_at.is_(None),
            )
        )
        existing_role = existing.scalar_one_or_none()
        if existing_role:
            existing_role.description = role_config["description"]
            existing_role.is_default = True
            _sync_role_permissions(existing_role, desired_permissions)
            await db.flush()
            await db.refresh(existing_role)
            created_roles.append(existing_role)
            continue
        
        # Create role
        role = Role(
            name=role_config["name"],
            description=role_config["description"],
            organization_id=org_id,
            is_default=True,
        )
        db.add(role)
        await db.flush()
        
        # Add permissions
        for perm_config in role_config["permissions"]:
            db.add(RolePermission(
                role_id=role.id,
                action=perm_config["action"],
                resource_type=perm_config["resource_type"],
            ))
        
        await db.flush()
        await db.refresh(role)
        created_roles.append(role)
    
    return created_roles


async def get_default_owner_role(db: AsyncSession, org_id: str) -> Role | None:
    """Get the default owner role for an organization."""
    from app.enterprise.modules.rbac.constants import OWNER_ROLE_ALIASES

    for role_name in OWNER_ROLE_ALIASES:
        result = await db.execute(
            select(Role).where(
                Role.organization_id == org_id,
                Role.name == role_name,
                Role.deleted_at.is_(None),
            )
        )
        role = result.scalar_one_or_none()
        if role:
            return role

    return None


async def list_roles(db: AsyncSession, org_id: str, offset: int = 0, limit: int = 50) -> tuple[list[Role], int]:
    # Get total count
    count_result = await db.execute(
        select(func.count(Role.id)).where(
            Role.organization_id == org_id,
            Role.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Role).where(
            Role.organization_id == org_id,
            Role.deleted_at.is_(None),
        ).order_by(Role.created_at).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_role(db: AsyncSession, org_id: str, role_id: str) -> Role:
    result = await db.execute(
        select(Role).where(
            Role.id == role_id,
            Role.organization_id == org_id,
            Role.deleted_at.is_(None),
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundError("Role not found")
    return role


async def update_role(db: AsyncSession, org_id: str, role_id: str, data: RoleUpdate) -> Role:
    role = await get_role(db, org_id, role_id)

    if role.is_default:
        raise ForbiddenError("System roles cannot be modified")

    if data.name is not None:
        from app.enterprise.modules.rbac.constants import SYSTEM_ROLE_NAMES

        normalized_system_names = {name.lower() for name in SYSTEM_ROLE_NAMES}
        if data.name.strip().lower() in normalized_system_names:
            raise BadRequestError("Role name is reserved for system roles")
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.is_default is not None:
        raise BadRequestError("Default status is reserved for system-managed roles")

    if data.permissions is not None:
        desired_permissions = {
            (permission.action, permission.resource_type)
            for permission in data.permissions
        }
        _sync_role_permissions(role, desired_permissions)

    await db.flush()
    await db.refresh(role)
    return role


async def delete_role(db: AsyncSession, org_id: str, role_id: str) -> Role:
    role = await get_role(db, org_id, role_id)
    if role.is_default:
        raise ForbiddenError("System roles cannot be deleted")

    now = utc_now()
    role.deleted_at = now
    for perm in role.permissions:
        perm.deleted_at = now
    await db.flush()
    await db.refresh(role)
    return role


# ──────────────────── User-Role Assignments ────────────────────

async def assign_role(
    db: AsyncSession, org_id: str, user_id: str, role_id: str,
    assigned_by: str | None = None, expires_at: datetime | None = None
) -> UserRoleAssignment:
    await get_role(db, org_id, role_id)

    existing = await db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id,
            UserRoleAssignment.organization_id == org_id,
            UserRoleAssignment.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError("User already has this role in this organization")

    assignment = UserRoleAssignment(
        user_id=user_id,
        role_id=role_id,
        organization_id=org_id,
        assigned_by=assigned_by,
        expires_at=expires_at
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


async def list_user_roles(
    db: AsyncSession, org_id: str, user_id: str | None = None, offset: int = 0, limit: int = 50
) -> tuple[list[UserRoleAssignment], int]:
    now = utc_now()
    base_stmt = select(UserRoleAssignment).where(
        UserRoleAssignment.organization_id == org_id,
        UserRoleAssignment.deleted_at.is_(None),
        or_(
            UserRoleAssignment.expires_at.is_(None),
            UserRoleAssignment.expires_at > now,
        ),
    )
    if user_id:
        base_stmt = base_stmt.where(UserRoleAssignment.user_id == user_id)

    # Get total count
    count_stmt = select(func.count(UserRoleAssignment.id)).where(
        UserRoleAssignment.organization_id == org_id,
        UserRoleAssignment.deleted_at.is_(None),
        or_(
            UserRoleAssignment.expires_at.is_(None),
            UserRoleAssignment.expires_at > now,
        ),
    )
    if user_id:
        count_stmt = count_stmt.where(UserRoleAssignment.user_id == user_id)

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    result = await db.execute(base_stmt.order_by(UserRoleAssignment.created_at).offset(offset).limit(limit))
    return list(result.scalars().all()), total


async def revoke_role(db: AsyncSession, org_id: str, assignment_id: str) -> UserRoleAssignment:
    result = await db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.id == assignment_id,
            UserRoleAssignment.organization_id == org_id,
            UserRoleAssignment.deleted_at.is_(None),
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise NotFoundError("Role assignment not found")
    assignment.deleted_at = utc_now()
    await db.flush()
    await db.refresh(assignment)
    return assignment


# ──────────────────── ABAC Policies ────────────────────

async def create_abac_policy(
    db: AsyncSession, org_id: str, data: ABACPolicyCreate
) -> ABACPolicy:
    policy = ABACPolicy(
        name=data.name,
        description=data.description,
        organization_id=org_id,
        resource_type=data.resource_type,
        action=data.action,
        attribute_key=data.attribute_key,
        operator=data.operator,
        attribute_value=data.attribute_value,
        effect_allow=data.effect_allow,
        active=data.active,
    )
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


async def list_abac_policies(db: AsyncSession, org_id: str, offset: int = 0, limit: int = 50) -> tuple[list[ABACPolicy], int]:
    # Get total count
    count_result = await db.execute(
        select(func.count(ABACPolicy.id)).where(
            ABACPolicy.organization_id == org_id,
            ABACPolicy.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ABACPolicy).where(
            ABACPolicy.organization_id == org_id,
            ABACPolicy.deleted_at.is_(None),
        ).order_by(ABACPolicy.created_at).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_abac_policy(db: AsyncSession, org_id: str, policy_id: str) -> ABACPolicy:
    result = await db.execute(
        select(ABACPolicy).where(
            ABACPolicy.id == policy_id,
            ABACPolicy.organization_id == org_id,
            ABACPolicy.deleted_at.is_(None),
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise NotFoundError("ABAC policy not found")
    return policy


async def update_abac_policy(
    db: AsyncSession, org_id: str, policy_id: str, data: ABACPolicyUpdate
) -> ABACPolicy:
    policy = await get_abac_policy(db, org_id, policy_id)
    for field in (
        "name", "description", "resource_type", "action",
        "attribute_key", "operator", "attribute_value", "effect_allow", "active",
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(policy, field, value)
    await db.flush()
    await db.refresh(policy)
    return policy


async def delete_abac_policy(db: AsyncSession, org_id: str, policy_id: str) -> ABACPolicy:
    policy = await get_abac_policy(db, org_id, policy_id)
    policy.deleted_at = utc_now()
    await db.flush()
    await db.refresh(policy)
    return policy


# ──────────────────── Access Reviews ────────────────────

async def create_access_review(
    db: AsyncSession, org_id: str, reviewer_id: str, data: AccessReviewCreate
) -> AccessReview:
    await get_role(db, org_id, data.role_id)
    review = AccessReview(
        organization_id=org_id,
        user_id=data.user_id,
        reviewer_id=reviewer_id,
        role_id=data.role_id,
        notes=data.notes,
    )
    db.add(review)
    await db.flush()
    await db.refresh(review)
    return review


async def list_access_reviews(
    db: AsyncSession, org_id: str, status: AccessReviewStatus | None = None
) -> list[AccessReview]:
    stmt = select(AccessReview).where(
        AccessReview.organization_id == org_id,
        AccessReview.deleted_at.is_(None),
    )
    if status:
        stmt = stmt.where(AccessReview.status == status)
    result = await db.execute(stmt.order_by(AccessReview.created_at.desc()))
    return list(result.scalars().all())


async def decide_access_review(
    db: AsyncSession, org_id: str, review_id: str, decision: AccessReviewDecision
) -> AccessReview:
    result = await db.execute(
        select(AccessReview).where(
            AccessReview.id == review_id,
            AccessReview.organization_id == org_id,
            AccessReview.deleted_at.is_(None),
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise NotFoundError("Access review not found")
    if review.status != AccessReviewStatus.PENDING:
        raise BadRequestError("Review already decided")
    review.status = decision.status
    if decision.notes is not None:
        review.notes = decision.notes
    await db.flush()
    await db.refresh(review)
    return review


# ──────────────────── Permission Check ────────────────────

def _evaluate_abac(policy: ABACPolicy, attributes: dict[str, str]) -> bool:
    attr_val = attributes.get(policy.attribute_key)
    if attr_val is None:
        return False
    op = policy.operator
    if op == ABACOperator.EQUALS:
        return attr_val == policy.attribute_value
    if op == ABACOperator.NOT_EQUALS:
        return attr_val != policy.attribute_value
    if op == ABACOperator.IN:
        return attr_val in [v.strip() for v in policy.attribute_value.split(",")]
    if op == ABACOperator.NOT_IN:
        return attr_val not in [v.strip() for v in policy.attribute_value.split(",")]
    if op == ABACOperator.CONTAINS:
        return policy.attribute_value in attr_val
    if op == ABACOperator.STARTS_WITH:
        return attr_val.startswith(policy.attribute_value)
    return False


async def check_permission(
    db: AsyncSession, org_id: str, req: PermissionCheckRequest
) -> PermissionCheckResponse:
    assignments, _ = await list_user_roles(db, org_id, user_id=req.user_id)
    matched_roles: list[str] = []
    for assignment in assignments:
        role = assignment.role
        for perm in role.permissions:
            if perm.deleted_at is not None:
                continue
            if perm.resource_type == req.resource_type and perm.action in (
                req.action, PermissionAction.MANAGE
            ):
                matched_roles.append(role.name)
                break

    policies, _ = await list_abac_policies(db, org_id)
    matched_policies: list[str] = []
    for policy in policies:
        if not policy.active:
            continue
        if policy.resource_type != req.resource_type or policy.action != req.action:
            continue
        if _evaluate_abac(policy, req.resource_attributes):
            matched_policies.append(policy.name)

    allowed = bool(matched_roles) or any(
        p.effect_allow
        for p in policies
        if p.active
        and p.resource_type == req.resource_type
        and p.action == req.action
        and p.name in matched_policies
    )

    # Fallback: if user has no roles assigned, check if they're the org owner
    # This allows existing users to access resources before RBAC is fully configured
    if (
        settings.RBAC_LEGACY_MEMBER_FALLBACK_ENABLED
        and not allowed
        and not assignments
    ):
        from app.organizations.models import Employee
        from app.security.audit_logger import audit_log
        result = await db.execute(
            select(Employee).where(
                Employee.organization_id == org_id,
                Employee.auth_user_id == req.user_id,
                Employee.deleted_at.is_(None),
            )
        )
        employee = result.scalar_one_or_none()
        # Grant access if user is an active member (fallback for non-enterprise)
        if employee:
            # Allow read/manage access as fallback for existing organizations
            # without RBAC setup
            audit_log(
                event_type="RBAC_LEGACY_FALLBACK_USED",
                user_id=req.user_id,
                organization_id=org_id,
                details={"resource_type": req.resource_type, "action": req.action},
                severity="HIGH",
            )
            allowed = True
            matched_roles.append("fallback_member")

    return PermissionCheckResponse(
        allowed=allowed,
        matched_roles=matched_roles,
        matched_policies=matched_policies,
    )


# ──────────────────── Overview ────────────────────

async def get_rbac_overview(db: AsyncSession, org_id: str) -> dict:
    roles, _ = await list_roles(db, org_id)

    assign_count = await db.execute(
        select(func.count(UserRoleAssignment.id)).where(
            UserRoleAssignment.organization_id == org_id,
            UserRoleAssignment.deleted_at.is_(None),
        )
    )
    total_assignments = assign_count.scalar_one()

    policy_count = await db.execute(
        select(func.count(ABACPolicy.id)).where(
            ABACPolicy.organization_id == org_id,
            ABACPolicy.deleted_at.is_(None),
        )
    )
    total_abac_policies = policy_count.scalar_one()

    review_count = await db.execute(
        select(func.count(AccessReview.id)).where(
            AccessReview.organization_id == org_id,
            AccessReview.status == AccessReviewStatus.PENDING,
            AccessReview.deleted_at.is_(None),
        )
    )
    pending_reviews = review_count.scalar_one()

    sso_configs = await list_sso_configs(db, org_id)

    return {
        "total_roles": len(roles),
        "total_assignments": total_assignments,
        "total_abac_policies": total_abac_policies,
        "pending_reviews": pending_reviews,
        "sso_configs": sso_configs,
        "roles": roles,
    }


# ──────────────────── SSO Configs ────────────────────

async def create_sso_config(
    db: AsyncSession, org_id: str, data: SSOConfigCreate
) -> SSOConfig:
    existing = await db.execute(
        select(SSOConfig).where(
            SSOConfig.organization_id == org_id,
            SSOConfig.provider == data.provider,
            SSOConfig.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"SSO config for provider '{data.provider}' already exists")

    config = SSOConfig(
        organization_id=org_id,
        provider=data.provider,
        issuer_url=data.issuer_url,
        client_id=data.client_id,
        metadata_url=data.metadata_url,
        enabled=data.enabled,
        auto_provision_roles=data.auto_provision_roles,
        default_role_id=data.default_role_id,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


async def list_sso_configs(db: AsyncSession, org_id: str) -> list[SSOConfig]:
    result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.organization_id == org_id,
            SSOConfig.deleted_at.is_(None),
        ).order_by(SSOConfig.created_at)
    )
    return list(result.scalars().all())


async def get_sso_config(db: AsyncSession, org_id: str, config_id: str) -> SSOConfig:
    result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.id == config_id,
            SSOConfig.organization_id == org_id,
            SSOConfig.deleted_at.is_(None),
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundError("SSO config not found")
    return config


async def update_sso_config(
    db: AsyncSession, org_id: str, config_id: str, data: SSOConfigUpdate
) -> SSOConfig:
    config = await get_sso_config(db, org_id, config_id)
    for field in (
        "issuer_url", "client_id", "metadata_url",
        "enabled", "auto_provision_roles", "default_role_id",
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(config, field, value)
    await db.flush()
    await db.refresh(config)
    return config


async def delete_sso_config(db: AsyncSession, org_id: str, config_id: str) -> SSOConfig:
    config = await get_sso_config(db, org_id, config_id)
    config.deleted_at = utc_now()
    await db.flush()
    await db.refresh(config)
    return config
