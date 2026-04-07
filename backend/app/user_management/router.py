"""API router for User Management endpoints."""

from datetime import datetime
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member
from app.shared.enums import UserStatus
from app.user_management.dependencies import require_read_users, require_manage_users
from app.user_management.enums import UserAction
from app.user_management.schemas import (
    ActivityLogEntry,
    ActivityLogFilter,
    ActivityLogListResponse,
    BulkInviteResponse,
    EffectivePermissionsResponse,
    InvitationAcceptRequest,
    InvitationDetail,
    UserDetail,
    UserInviteBulkRequest,
    UserInviteRequest,
    UserInviteResponse,
    UserListFilters,
    UserListItem,
    UserRoleAssignmentResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.user_management.service import (
    accept_invitation,
    activate_user,
    bulk_create_invitations,
    create_invitation,
    get_effective_permissions,
    get_invitation_by_token,
    get_user_activity_log,
    get_user_detail,
    list_organization_users,
    log_user_activity,
    remove_user_from_organization,
    suspend_user,
    update_user,
    update_user_roles,
)

router = APIRouter(tags=["User Management"])


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


# ============== User List & Detail Endpoints ==============

@router.get(
    "/organizations/{org_id}/users",
    response_model=dict,  # Paginated result with UserListItem
    dependencies=[Depends(require_read_users)]
)
async def list_users(
    org_id: str,
    status: UserStatus | None = Query(None, description="Filter by user status"),
    role_id: str | None = Query(None, description="Filter by role ID"),
    department: str | None = Query(None, description="Filter by department"),
    search: str | None = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List users in an organization with filtering and pagination."""
    filters = UserListFilters(
        status=status,
        role_id=role_id,
        department=department,
        search=search,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    result = await list_organization_users(db, org_id, filters)
    
    # Log view action
    await log_user_activity(
        db, current_user.id, org_id, UserAction.READ,
        current_user.id, resource_type="user_list"
    )
    
    return result


@router.get(
    "/organizations/{org_id}/users/{user_id}",
    response_model=UserDetail,
    dependencies=[Depends(require_read_users)]
)
async def get_user(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific user."""
    return await get_user_detail(db, org_id, user_id)


@router.patch(
    "/organizations/{org_id}/users/{user_id}",
    response_model=UserListItem,
    dependencies=[Depends(require_manage_users)]
)
async def update_user_endpoint(
    org_id: str,
    user_id: str,
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user details (name, department, job title, status)."""
    return await update_user(db, org_id, user_id, data, current_user.id)


# ============== User Status Management Endpoints ==============

@router.post(
    "/organizations/{org_id}/users/{user_id}/suspend",
    response_model=UserListItem,
    dependencies=[Depends(require_manage_users)]
)
async def suspend_user_endpoint(
    org_id: str,
    user_id: str,
    data: UserStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suspend a user account (temporarily disable)."""
    return await suspend_user(db, org_id, user_id, data, current_user.id)


@router.post(
    "/organizations/{org_id}/users/{user_id}/activate",
    response_model=UserListItem,
    dependencies=[Depends(require_manage_users)]
)
async def activate_user_endpoint(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate/reactivate a user account."""
    return await activate_user(db, org_id, user_id, current_user.id)


@router.delete(
    "/organizations/{org_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_manage_users)]
)
async def remove_user_endpoint(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a user from the organization (soft delete)."""
    await remove_user_from_organization(db, org_id, user_id, current_user.id)
    return None


# ============== Invitation Endpoints ==============

@router.post(
    "/organizations/{org_id}/users/invite",
    response_model=UserInviteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_manage_users)]
)
async def invite_user(
    org_id: str,
    data: UserInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new user to the organization."""
    await create_invitation(db, org_id, current_user.id, data)
    await db.commit()
    return {"success": True, "message": "Invitation sent successfully"}


@router.post(
    "/organizations/{org_id}/users/invite-bulk",
    response_model=BulkInviteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_manage_users)]
)
async def invite_users_bulk(
    org_id: str,
    data: UserInviteBulkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite multiple users to the organization."""
    return await bulk_create_invitations(db, org_id, current_user.id, data)


@router.get(
    "/invitations/{token}",
    response_model=InvitationDetail
)
async def get_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Get invitation details by token (public endpoint for acceptance page)."""
    return await get_invitation_by_token(db, token)


@router.post(
    "/invitations/{token}/accept",
    status_code=status.HTTP_201_CREATED
)
async def accept_invitation_endpoint(
    token: str,
    data: InvitationAcceptRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Accept an invitation and create user account."""
    user = await accept_invitation(db, token, data)
    await db.commit()
    
    from app.auth.service import create_access_token
    from app.auth.schemas import TokenResponse, UserResponse
    
    session_id = secrets.token_urlsafe(32)
    access_token = create_access_token(user.id, session_id)
    secure = _is_secure_request(request)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }


# ============== Role Management Endpoints ==============

@router.get(
    "/organizations/{org_id}/users/{user_id}/roles",
    response_model=list[UserRoleAssignmentResponse],
    dependencies=[Depends(require_read_users)]
)
async def get_user_roles(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get role assignments for a user."""
    from app.enterprise.modules.rbac.service import list_user_roles

    assignments, _ = await list_user_roles(db, org_id, user_id=user_id)
    
    return [
        UserRoleAssignmentResponse(
            id=a.id,
            user_id=a.user_id,
            role_id=a.role_id,
            role={"id": a.role.id, "name": a.role.name, "description": a.role.description},
            organization_id=a.organization_id,
            assigned_by=a.assigned_by,
            assigned_at=a.assigned_at,
            expires_at=a.expires_at
        )
        for a in assignments
    ]


@router.patch(
    "/organizations/{org_id}/users/{user_id}/roles",
    response_model=list[UserRoleAssignmentResponse],
    dependencies=[Depends(require_manage_users)]
)
async def update_user_roles_endpoint(
    org_id: str,
    user_id: str,
    data: UserRoleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update role assignments for a user."""
    return await update_user_roles(db, org_id, user_id, data, current_user.id)


# ============== Permission Endpoints ==============

@router.get(
    "/organizations/{org_id}/users/{user_id}/permissions",
    response_model=EffectivePermissionsResponse,
    dependencies=[Depends(require_read_users)]
)
async def get_user_permissions(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get effective permissions for a user."""
    return await get_effective_permissions(db, org_id, user_id)


# ============== Activity Log Endpoints ==============

@router.get(
    "/organizations/{org_id}/users/{user_id}/activity",
    response_model=ActivityLogListResponse,
    dependencies=[Depends(require_read_users)]
)
async def get_user_activity(
    org_id: str,
    user_id: str,
    action: UserAction | None = Query(None),
    resource_type: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get activity log for a specific user."""
    filters = ActivityLogFilter(
        action=action,
        resource_type=resource_type,
        from_date=from_date,
        to_date=to_date
    )
    
    result = await get_user_activity_log(db, org_id, user_id, filters, page, limit)
    
    return ActivityLogListResponse(
        items=result["items"],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        pages=result["pages"]
    )


@router.get(
    "/organizations/{org_id}/activity",
    response_model=ActivityLogListResponse,
    dependencies=[Depends(require_manage_users)]
)
async def get_organization_activity(
    org_id: str,
    action: UserAction | None = Query(None),
    resource_type: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get activity log for the entire organization (admin only)."""
    filters = ActivityLogFilter(
        action=action,
        resource_type=resource_type,
        from_date=from_date,
        to_date=to_date
    )
    
    result = await get_user_activity_log(db, org_id, None, filters, page, limit)
    
    return ActivityLogListResponse(
        items=result["items"],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        pages=result["pages"]
    )
