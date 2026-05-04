"""User Management service layer for user lifecycle and access control."""

from datetime import timedelta, timezone
import secrets
from typing import Any

from sqlalchemy import func, select, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.auth.service import hash_password
from app.enterprise.modules.rbac.models import Role, UserRoleAssignment
from app.enterprise.modules.rbac.service import (
    assign_role as rbac_assign_role,
    revoke_role as rbac_revoke_role,
    list_user_roles,
)
from app.organizations.models import Employee, Organization
from app.shared.enums import UserStatus
from app.shared.exceptions import ConflictError, NotFoundError, BadRequestError, ForbiddenError
from app.shared.utils.time import utc_now
from app.user_management.enums import InvitationStatus, UserAction
from app.user_management.models import UserActivityLog, UserInvitation, UserPreferences
from app.user_management.schemas import (
    ActivityLogFilter,
    BulkInviteResponse,
    EffectivePermissionsResponse,
    InvitationAcceptRequest,
    InvitationDetail,
    RoleSummary,
    UserActivitySummary,
    UserDetail,
    UserInviteBulkRequest,
    UserInviteRequest,
    UserInviteResponse,
    UserListFilters,
    UserListItem,
    UserPermissionResponse,
    UserRoleAssignmentResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)


# ============== Constants ==============

INVITATION_EXPIRY_DAYS = 7
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30


# ============== User List & Detail Services ==============

async def list_organization_users(
    db: AsyncSession,
    org_id: str,
    filters: UserListFilters
) -> dict[str, Any]:
    """List users in an organization with filtering, sorting, and pagination."""
    
    # Build base query
    stmt = (
        select(User, Employee)
        .join(Employee, Employee.auth_user_id == User.id)
        .where(
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
            User.deleted_at.is_(None)
        )
    )
    
    # Apply filters
    if filters.status:
        stmt = stmt.where(User.status == filters.status)
    
    if filters.department:
        stmt = stmt.where(Employee.department == filters.department)
    
    if filters.search:
        search_term = f"%{filters.search}%"
        stmt = stmt.where(
            (User.display_name.ilike(search_term)) |
            (User.email.ilike(search_term))
        )
    
    # Get total count before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()
    
    # Apply sorting
    sort_column = getattr(User, filters.sort_by, User.created_at)
    if filters.sort_order == "desc":
        stmt = stmt.order_by(desc(sort_column))
    else:
        stmt = stmt.order_by(asc(sort_column))
    
    # Apply pagination
    offset = (filters.page - 1) * filters.limit
    stmt = stmt.offset(offset).limit(filters.limit)
    
    # Execute query
    result = await db.execute(stmt)
    rows = result.all()
    
    # Build response items
    items = []
    for user, employee in rows:
        # Get user's roles
        role_assignments, _ = await list_user_roles(db, org_id, user_id=user.id)
        roles = [
            RoleSummary(
                id=ra.role.id,
                name=ra.role.name,
                description=ra.role.description
            )
            for ra in role_assignments
        ]
        
        items.append(UserListItem(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            status=UserStatus(user.status),
            is_active=user.is_active and user.status == UserStatus.ACTIVE,
            last_login=user.last_login,
            roles=roles,
            department=employee.department,
            job_title=employee.job_title,
            joined_at=employee.joined_at,
            created_at=user.created_at
        ))
    
    pages = (total + filters.limit - 1) // filters.limit
    
    return {
        "items": items,
        "total": total,
        "page": filters.page,
        "limit": filters.limit,
        "pages": pages
    }


async def get_user_detail(
    db: AsyncSession,
    org_id: str,
    user_id: str
) -> UserDetail:
    """Get detailed information about a user in an organization."""
    
    # Get user and employee
    stmt = (
        select(User, Employee)
        .join(Employee, Employee.auth_user_id == User.id)
        .where(
            User.id == user_id,
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
            User.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    
    if not row:
        raise NotFoundError("User not found in organization")
    
    user, employee = row
    
    # Get roles
    role_assignments, _ = await list_user_roles(db, org_id, user_id=user.id)
    roles = [
        RoleSummary(
            id=ra.role.id,
            name=ra.role.name,
            description=ra.role.description
        )
        for ra in role_assignments
    ]
    
    # Get activity summary
    activity_summary = await _get_user_activity_summary(db, user_id, org_id)
    
    # Get preferences
    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id).limit(1)
    )
    preferences = prefs_result.scalar_one_or_none()
    
    # Get effective permissions
    permissions = await _get_user_permissions(db, org_id, user_id, role_assignments)
    
    return UserDetail(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=UserStatus(user.status),
        is_active=user.is_active and user.status == UserStatus.ACTIVE,
        last_login=user.last_login,
        roles=roles,
        department=employee.department,
        job_title=employee.job_title,
        joined_at=employee.joined_at,
        created_at=user.created_at,
        preferences=preferences.notification_settings if preferences else None,
        activity_summary=activity_summary,
        permissions=permissions
    )


async def _get_user_activity_summary(
    db: AsyncSession,
    user_id: str,
    org_id: str
) -> UserActivitySummary:
    """Get activity summary for a user."""
    
    thirty_days_ago = utc_now() - timedelta(days=30)
    
    # Count logins in last 30 days
    login_stmt = select(func.count()).where(
        UserActivityLog.user_id == user_id,
        UserActivityLog.organization_id == org_id,
        UserActivityLog.action == UserAction.LOGIN,
        UserActivityLog.created_at >= thirty_days_ago
    )
    login_result = await db.execute(login_stmt)
    login_count = login_result.scalar_one()
    
    # Count all actions in last 30 days
    action_stmt = select(func.count()).where(
        UserActivityLog.user_id == user_id,
        UserActivityLog.organization_id == org_id,
        UserActivityLog.created_at >= thirty_days_ago
    )
    action_result = await db.execute(action_stmt)
    action_count = action_result.scalar_one()
    
    # Get last login
    last_login_stmt = select(UserActivityLog).where(
        UserActivityLog.user_id == user_id,
        UserActivityLog.organization_id == org_id,
        UserActivityLog.action == UserAction.LOGIN
    ).order_by(desc(UserActivityLog.created_at)).limit(1)
    
    last_login_result = await db.execute(last_login_stmt)
    last_login_log = last_login_result.scalar_one_or_none()
    
    # Get user last_login if no activity log
    if not last_login_log:
        user_stmt = select(User.last_login).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        last_login = user_result.scalar_one_or_none()
    else:
        last_login = last_login_log.created_at
    
    return UserActivitySummary(
        last_login=last_login,
        login_count_30d=login_count,
        actions_count_30d=action_count
    )


async def _get_user_permissions(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    role_assignments: list[UserRoleAssignment]
) -> list[UserPermissionResponse]:
    """Get effective permissions from role assignments."""
    
    permissions = []
    seen = set()
    
    for assignment in role_assignments:
        for perm in assignment.role.permissions:
            if perm.deleted_at is not None:
                continue
            
            key = (perm.action, perm.resource_type)
            if key not in seen:
                seen.add(key)
                permissions.append(UserPermissionResponse(
                    action=perm.action,
                    resource_type=perm.resource_type,
                    granted_via_role=assignment.role.name,
                    granted_via_abac=False
                ))
    
    return permissions


# ============== User Update Services ==============

async def update_user(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: UserUpdateRequest,
    updated_by: str
) -> UserListItem:
    """Update user details."""
    
    # Get user and employee
    stmt = (
        select(User, Employee)
        .join(Employee, Employee.auth_user_id == User.id)
        .where(
            User.id == user_id,
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
            User.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    
    if not row:
        raise NotFoundError("User not found in organization")
    
    user, employee = row
    
    # Update user fields
    if data.display_name is not None:
        user.display_name = data.display_name
        employee.name = data.display_name
    
    if data.is_active is not None:
        user.is_active = data.is_active
    
    # Update employee fields
    if data.department is not None:
        employee.department = data.department
    
    if data.job_title is not None:
        employee.job_title = data.job_title
    
    await db.flush()
    
    # Log activity
    await log_user_activity(
        db, user_id, org_id, UserAction.USER_UPDATED, updated_by,
        resource_type="user", resource_id=user_id,
        action_metadata={"updated_fields": [k for k, v in data.model_dump().items() if v is not None]}
    )
    
    # Return updated user
    return await get_user_list_item(db, org_id, user_id)


async def get_user_list_item(
    db: AsyncSession,
    org_id: str,
    user_id: str
) -> UserListItem:
    """Get a single user list item."""
    
    user, employee = await _get_user_employee(db, org_id, user_id)

    role_assignments, _ = await list_user_roles(db, org_id, user_id=user_id)
    roles = [
        RoleSummary(id=ra.role.id, name=ra.role.name, description=ra.role.description)
        for ra in role_assignments
    ]
    
    return UserListItem(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=UserStatus(user.status),
        is_active=user.is_active and user.status == UserStatus.ACTIVE,
        last_login=user.last_login,
        roles=roles,
        department=employee.department,
        job_title=employee.job_title,
        joined_at=employee.joined_at,
        created_at=user.created_at
    )


async def _get_user_employee(
    db: AsyncSession,
    org_id: str,
    user_id: str
) -> tuple[User, Employee]:
    """Get user and employee record."""
    
    stmt = (
        select(User, Employee)
        .join(Employee, Employee.auth_user_id == User.id)
        .where(
            User.id == user_id,
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
            User.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    
    if not row:
        raise NotFoundError("User not found in organization")
    
    return row


# ============== Invitation Services ==============

async def create_invitation(
    db: AsyncSession,
    org_id: str,
    invited_by: str,
    data: UserInviteRequest
) -> UserInviteResponse:
    """Create an invitation for a user to join an organization."""
    
    # Check if role exists
    role_stmt = select(Role).where(
        Role.id == data.role_id,
        Role.organization_id == org_id,
        Role.deleted_at.is_(None)
    ).limit(1)
    role_result = await db.execute(role_stmt)
    role = role_result.scalar_one_or_none()
    
    if not role:
        raise NotFoundError("Role not found")
    
    # Check if user already exists and is a member
    user_stmt = select(User).where(
        User.email == data.email,
        User.deleted_at.is_(None)
    ).limit(1)
    user_result = await db.execute(user_stmt)
    existing_user = user_result.scalar_one_or_none()
    
    if existing_user:
        # Check if already a member
        emp_stmt = select(Employee).where(
            Employee.auth_user_id == existing_user.id,
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None)
        ).limit(1)
        emp_result = await db.execute(emp_stmt)
        if emp_result.scalar_one_or_none():
            raise ConflictError("User is already a member of this organization")
    
    # Check for existing pending invitation
    existing_invite_stmt = select(UserInvitation).where(
        UserInvitation.email == data.email,
        UserInvitation.organization_id == org_id,
        UserInvitation.status == InvitationStatus.PENDING,
        UserInvitation.deleted_at.is_(None)
    ).limit(1)
    existing_invite_result = await db.execute(existing_invite_stmt)
    existing_invite = existing_invite_result.scalar_one_or_none()
    
    if existing_invite:
        # Update existing invitation
        existing_invite.status = InvitationStatus.REVOKED
        existing_invite.deleted_at = utc_now()

    # Create invitation
    token = secrets.token_urlsafe(48)
    invitation = UserInvitation(
        email=data.email,
        organization_id=org_id,
        invited_by=invited_by,
        role_id=data.role_id,
        token=token,
        status=InvitationStatus.PENDING,
        expires_at=utc_now() + timedelta(days=INVITATION_EXPIRY_DAYS)
    )
    
    db.add(invitation)
    await db.flush()
    
    # Log activity
    await log_user_activity(
        db, invited_by, org_id, UserAction.INVITATION_SENT, invited_by,
        resource_type="invitation", resource_id=invitation.id,
        action_metadata={"invited_email": data.email, "role_id": data.role_id}
    )
    
    return UserInviteResponse(
        id=invitation.id,
        email=invitation.email,
        invitation_token=token,
        status=InvitationStatus.PENDING.value,
        expires_at=invitation.expires_at,
    )


async def bulk_create_invitations(
    db: AsyncSession,
    org_id: str,
    invited_by: str,
    data: UserInviteBulkRequest
) -> BulkInviteResponse:
    """Create invitations for multiple users."""
    
    results = []
    successful = 0
    failed = 0
    
    for invite_data in data.invitations:
        try:
            result = await create_invitation(db, org_id, invited_by, invite_data)
            results.append(result)
            successful += 1
        except Exception as e:
            results.append(UserInviteResponse(
                id="",
                email=invite_data.email,
                status="failed",
                error=str(e),
                expires_at=utc_now()
            ))
            failed += 1
    
    await db.commit()
    
    return BulkInviteResponse(
        total=len(data.invitations),
        successful=successful,
        failed=failed,
        results=results
    )


async def get_invitation_by_token(
    db: AsyncSession,
    token: str
) -> InvitationDetail:
    """Get invitation details by token."""
    
    stmt = (
        select(UserInvitation)
        .where(
            UserInvitation.token == token,
            UserInvitation.deleted_at.is_(None)
        )
        .options(
            selectinload(UserInvitation.organization),
            selectinload(UserInvitation.inviter),
            selectinload(UserInvitation.role)
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()
    
    if not invitation:
        raise NotFoundError("Invitation not found")
    
    return InvitationDetail(
        token=invitation.token,
        email=invitation.email,
        organization_name=invitation.organization.name,
        invited_by_name=invitation.inviter.display_name,
        role_name=invitation.role.name if invitation.role else None,
        expires_at=invitation.expires_at,
        is_valid=invitation.is_valid()
    )


async def accept_invitation(
    db: AsyncSession,
    token: str,
    data: InvitationAcceptRequest
) -> User:
    """Accept an invitation and create user account."""
    
    # Get invitation
    stmt = (
        select(UserInvitation)
        .where(
            UserInvitation.token == token,
            UserInvitation.deleted_at.is_(None)
        )
        .options(
            selectinload(UserInvitation.organization),
            selectinload(UserInvitation.role)
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()
    
    if not invitation:
        raise NotFoundError("Invitation not found")
    
    if not invitation.is_valid():
        if invitation.is_expired():
            invitation.status = InvitationStatus.EXPIRED
            raise BadRequestError("Invitation has expired")
        raise BadRequestError("Invitation is no longer valid")
    
    # Check if user already exists
    user_stmt = select(User).where(
        User.email == invitation.email,
        User.deleted_at.is_(None)
    ).limit(1)
    user_result = await db.execute(user_stmt)
    existing_user = user_result.scalar_one_or_none()
    
    if existing_user:
        user = existing_user
        # Update display name if provided
        if data.display_name and data.display_name != user.display_name:
            user.display_name = data.display_name
    else:
        # Create new user
        user = User(
            email=invitation.email,
            display_name=data.display_name,
            hashed_password=hash_password(data.password),
            status=UserStatus.ACTIVE,
            is_active=True,
            verified=False  # Email verification required; user must verify email before full access
        )
        db.add(user)
        await db.flush()
    
    # Create employee record
    employee = Employee(
        name=data.display_name,
        organization_id=invitation.organization_id,
        auth_user_id=user.id,
        joined_at=utc_now()
    )
    db.add(employee)

    # Assign role if specified
    if invitation.role_id:
        await rbac_assign_role(
            db, invitation.organization_id, user.id, invitation.role_id
        )

    # Update invitation
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = utc_now()
    
    await db.flush()
    
    # Log activity
    await log_user_activity(
        db, user.id, invitation.organization_id,
        UserAction.INVITATION_ACCEPTED, user.id,
        resource_type="invitation", resource_id=invitation.id
    )
    
    await log_user_activity(
        db, user.id, invitation.organization_id,
        UserAction.ORG_JOINED, user.id,
        resource_type="organization", resource_id=invitation.organization_id
    )
    
    return user


# ============== Role Management Services ==============

async def update_user_roles(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: UserRoleUpdateRequest,
    updated_by: str
) -> list[UserRoleAssignmentResponse]:
    """Update user role assignments."""
    
    # Verify user exists in organization
    await _get_user_employee(db, org_id, user_id)
    
    if data.action == "replace":
        # Revoke all existing roles
        current_roles, _ = await list_user_roles(db, org_id, user_id=user_id)
        for assignment in current_roles:
            await rbac_revoke_role(db, org_id, assignment.id)
        
        # Assign new roles
        for role_id in data.role_ids:
            await rbac_assign_role(db, org_id, user_id, role_id)
    
    elif data.action == "assign":
        # Assign additional roles
        for role_id in data.role_ids:
            try:
                await rbac_assign_role(db, org_id, user_id, role_id)
            except ConflictError:
                # Role already assigned, skip
                pass
    
    elif data.action == "revoke":
        # Revoke specific roles
        current_roles, _ = await list_user_roles(db, org_id, user_id=user_id)
        for assignment in current_roles:
            if assignment.role_id in data.role_ids:
                await rbac_revoke_role(db, org_id, assignment.id)
    
    # Log activity
    await log_user_activity(
        db, user_id, org_id,
        UserAction.ROLE_ASSIGNED if data.action in ["assign", "replace"] else UserAction.ROLE_REVOKED,
        updated_by,
        resource_type="user", resource_id=user_id,
        action_metadata={"action": data.action, "role_ids": data.role_ids, "reason": data.reason}
    )

    # Return updated assignments
    assignments, _ = await list_user_roles(db, org_id, user_id=user_id)
    return [
        UserRoleAssignmentResponse(
            id=a.id,
            user_id=a.user_id,
            role_id=a.role_id,
            role=RoleSummary(id=a.role.id, name=a.role.name, description=a.role.description),
            organization_id=a.organization_id,
            assigned_by=a.assigned_by,
            assigned_at=a.assigned_at,
            expires_at=a.expires_at
        )
        for a in assignments
    ]


# ============== Activity Log Services ==============

async def log_user_activity(
    db: AsyncSession,
    user_id: str,
    org_id: str,
    action: UserAction,
    performed_by: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    action_metadata: dict[str, Any] | None = None
) -> UserActivityLog:
    """Log a user activity for audit trail."""
    
    log_entry = UserActivityLog(
        user_id=user_id,
        organization_id=org_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        action_metadata=action_metadata
    )
    
    db.add(log_entry)
    await db.flush()
    
    return log_entry


async def get_user_activity_log(
    db: AsyncSession,
    org_id: str,
    user_id: str | None,
    filters: ActivityLogFilter,
    page: int = 1,
    limit: int = 20
) -> dict[str, Any]:
    """Get activity log for a user or organization."""
    
    stmt = select(UserActivityLog).where(
        UserActivityLog.organization_id == org_id
    )
    
    if user_id:
        stmt = stmt.where(UserActivityLog.user_id == user_id)
    
    if filters.action:
        stmt = stmt.where(UserActivityLog.action == filters.action)
    
    if filters.resource_type:
        stmt = stmt.where(UserActivityLog.resource_type == filters.resource_type)
    
    if filters.from_date:
        stmt = stmt.where(UserActivityLog.created_at >= filters.from_date)
    
    if filters.to_date:
        stmt = stmt.where(UserActivityLog.created_at <= filters.to_date)
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()
    
    # Apply sorting and pagination
    stmt = stmt.order_by(desc(UserActivityLog.created_at))
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    pages = (total + limit - 1) // limit
    
    return {
        "items": logs,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }


# ============== Status Management Services ==============

async def suspend_user(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: UserStatusUpdateRequest,
    suspended_by: str
) -> UserListItem:
    """Suspend a user account."""
    
    user, _ = await _get_user_employee(db, org_id, user_id)
    
    # Prevent self-suspension
    if user_id == suspended_by:
        raise ForbiddenError("Cannot suspend your own account")
    
    user.status = UserStatus.SUSPENDED
    user.is_active = False
    
    await db.flush()
    
    # Log activity
    await log_user_activity(
        db, user_id, org_id, UserAction.USER_SUSPENDED, suspended_by,
        resource_type="user", resource_id=user_id,
        action_metadata={"reason": data.reason}
    )
    
    return await get_user_list_item(db, org_id, user_id)


async def activate_user(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    activated_by: str
) -> UserListItem:
    """Activate/reactivate a user account."""
    
    user, _ = await _get_user_employee(db, org_id, user_id)
    
    user.status = UserStatus.ACTIVE
    user.is_active = True
    user.failed_login_attempts = 0
    user.locked_until = None
    
    await db.flush()
    
    # Log activity
    await log_user_activity(
        db, user_id, org_id, UserAction.USER_ACTIVATED, activated_by,
        resource_type="user", resource_id=user_id
    )
    
    return await get_user_list_item(db, org_id, user_id)


async def admin_reset_user_password(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    new_password: str,
    reset_by: str
) -> UserListItem:
    """Admin-initiated password reset for a user."""
    from app.auth.service import hash_password

    user, _ = await _get_user_employee(db, org_id, user_id)

    # Prevent resetting own password via admin endpoint (use /auth/me for that)
    if user_id == reset_by:
        raise ForbiddenError("Cannot reset your own password via admin endpoint. Use the Settings page instead.")

    user.hashed_password = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    await db.flush()

    # Log activity
    await log_user_activity(
        db, user_id, org_id, UserAction.PASSWORD_RESET_COMPLETED, reset_by,
        resource_type="user", resource_id=user_id,
        action_metadata={"reset_by_admin": True}
    )

    return await get_user_list_item(db, org_id, user_id)


async def remove_user_from_organization(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    removed_by: str
) -> None:
    """Remove a user from an organization (soft delete employee record)."""
    
    user, employee = await _get_user_employee(db, org_id, user_id)
    
    # Prevent self-removal
    if user_id == removed_by:
        raise ForbiddenError("Cannot remove yourself from organization")
    
    # Soft delete employee record
    employee.deleted_at = utc_now()

    # Revoke all roles
    current_roles, _ = await list_user_roles(db, org_id, user_id=user_id)
    for assignment in current_roles:
        await rbac_revoke_role(db, org_id, assignment.id)
    
    await db.flush()
    
    # Log activity
    await log_user_activity(
        db, user_id, org_id, UserAction.USER_REMOVED, removed_by,
        resource_type="user", resource_id=user_id
    )
    
    await log_user_activity(
        db, user_id, org_id, UserAction.ORG_LEFT, user_id,
        resource_type="organization", resource_id=org_id,
        action_metadata={"removed_by": removed_by}
    )


# ============== Effective Permissions Service ==============

async def get_effective_permissions(
    db: AsyncSession,
    org_id: str,
    user_id: str
) -> EffectivePermissionsResponse:
    """Get effective permissions for a user."""

    # Get user roles
    assignments, _ = await list_user_roles(db, org_id, user_id=user_id)
    
    roles = []
    permissions = []
    seen_perms = set()
    
    for assignment in assignments:
        roles.append(RoleSummary(
            id=assignment.role.id,
            name=assignment.role.name,
            description=assignment.role.description
        ))
        
        for perm in assignment.role.permissions:
            if perm.deleted_at is not None:
                continue
            
            key = (perm.action, perm.resource_type)
            if key not in seen_perms:
                seen_perms.add(key)
                permissions.append(UserPermissionResponse(
                    action=perm.action,
                    resource_type=perm.resource_type,
                    granted_via_role=assignment.role.name,
                    granted_via_abac=False
                ))
    
    # TODO: Add ABAC policy evaluation
    abac_policies = []
    
    return EffectivePermissionsResponse(
        user_id=user_id,
        organization_id=org_id,
        roles=roles,
        permissions=permissions,
        abac_policies=abac_policies,
        calculated_at=utc_now()
    )
