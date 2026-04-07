"""Reusable RBAC permission dependencies for organization-scoped endpoints."""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.enterprise.modules.rbac.schemas import PermissionCheckRequest
from app.enterprise.modules.rbac.service import check_permission
from app.organizations.models import Employee
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.exceptions import ForbiddenError
from app.shared.org_access import get_current_org_member


async def ensure_org_permission(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    action: PermissionAction,
    resource_type: RBACResourceType,
) -> None:
    """Validate RBAC permission for a user in an organization context."""
    result = await check_permission(
        db,
        org_id,
        PermissionCheckRequest(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
        ),
    )

    if not result.allowed:
        raise ForbiddenError(
            f"Missing permission: {action.value} on {resource_type.value}"
        )


def require_org_permission(
    action: PermissionAction,
    resource_type: RBACResourceType,
    org_id_param: str = "org_id",
):
    """Create a dependency that enforces an org-scoped RBAC permission."""

    async def checker(
        request: Request,
        member: Employee = Depends(get_current_org_member),
        db: AsyncSession = Depends(get_db),
    ) -> Employee:
        org_id = request.path_params.get(org_id_param)
        if not org_id:
            raise ForbiddenError("Organization ID not found in request")

        await ensure_org_permission(
            db,
            org_id,
            member.auth_user_id,
            action,
            resource_type,
        )
        return member

    return checker
