from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.enterprise.modules.rbac.dependencies import require_org_permission
from app.organizations.models import Employee
from app.notifications.schemas import (
    NotificationPreferencesUpdate,
    NotificationPreferencesResponse,
    NotificationPrefResponse,
    NotificationLogsResponse,
    NotificationLogResponse,
    SendTestEmailRequest,
    PaginatedNotificationLogs,
)
from app.notifications.service import (
    get_preferences,
    update_preferences,
    get_notification_logs,
    send_test_notification,
)
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member
from app.shared.pagination import PaginatedResponse

router = APIRouter()


@router.get(
    "/organizations/{org_id}/notifications/preferences",
    response_model=NotificationPreferencesResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.NOTIFICATION))],
)
async def get_notification_preferences(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    prefs = await get_preferences(db, member.auth_user_id, org_id)
    return NotificationPreferencesResponse(
        preferences=[NotificationPrefResponse.model_validate(p) for p in prefs]
    )


@router.put(
    "/organizations/{org_id}/notifications/preferences",
    response_model=NotificationPreferencesResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.UPDATE, RBACResourceType.NOTIFICATION))],
)
async def save_notification_preferences(
    org_id: str,
    data: NotificationPreferencesUpdate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    prefs = await update_preferences(db, member.auth_user_id, org_id, data.preferences)
    return NotificationPreferencesResponse(
        preferences=[NotificationPrefResponse.model_validate(p) for p in prefs]
    )


@router.get(
    "/organizations/{org_id}/notifications/history",
    response_model=PaginatedNotificationLogs,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.NOTIFICATION))],
)
async def get_notification_history(
    org_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    logs, total = await get_notification_logs(db, member.auth_user_id, org_id, limit=page_size, offset=offset)
    return PaginatedResponse.create(
        items=[NotificationLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/organizations/{org_id}/notifications/test",
    response_model=NotificationLogResponse,
    status_code=201,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.NOTIFICATION))],
)
async def send_test_email(
    org_id: str,
    data: SendTestEmailRequest,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log = await send_test_notification(db, current_user, org_id, data.notification_type)
    return NotificationLogResponse.model_validate(log)
