"""Dependencies for User Management permission checking."""

from typing import Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from app.enterprise.modules.rbac.schemas import PermissionCheckRequest
from app.enterprise.modules.rbac.service import check_permission as rbac_check_permission
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.exceptions import ForbiddenError


def require_permission(
    action: PermissionAction,
    resource_type: RBACResourceType,
    org_id_param: str = "org_id"
) -> Callable:
    """Factory for creating permission check dependencies.
    
    Usage:
        @router.post(
            "/{org_id}/users",
            dependencies=[Depends(require_permission(PermissionAction.CREATE, RBACResourceType.USER))]
        )
        async def create_user(...):
            pass
    """
    async def checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        org_id = request.path_params.get(org_id_param)
        
        if not org_id:
            raise ForbiddenError("Organization ID not found in request")
        
        # Check if user has the required permission
        result = await rbac_check_permission(
            db, org_id,
            PermissionCheckRequest(
                user_id=current_user.id,
                action=action,
                resource_type=resource_type
            )
        )
        
        if not result.allowed:
            raise ForbiddenError(
                f"Missing permission: {action.value} on {resource_type.value}"
            )
        
        return current_user
    
    return checker


async def require_manage_users(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require MANAGE permission on USER resource type."""
    org_id = request.path_params.get("org_id")
    
    if not org_id:
        raise ForbiddenError("Organization ID not found in request")
    
    from app.enterprise.modules.rbac.schemas import PermissionCheckRequest
    
    result = await rbac_check_permission(
        db, org_id,
        PermissionCheckRequest(
            user_id=current_user.id,
            action=PermissionAction.MANAGE,
            resource_type=RBACResourceType.USER
        )
    )
    
    if not result.allowed:
        raise ForbiddenError("You don't have permission to manage users")
    
    return current_user


async def require_read_users(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require READ permission on USER resource type."""
    org_id = request.path_params.get("org_id")
    
    if not org_id:
        raise ForbiddenError("Organization ID not found in request")
    
    from app.enterprise.modules.rbac.schemas import PermissionCheckRequest
    
    result = await rbac_check_permission(
        db, org_id,
        PermissionCheckRequest(
            user_id=current_user.id,
            action=PermissionAction.READ,
            resource_type=RBACResourceType.USER
        )
    )
    
    if not result.allowed:
        raise ForbiddenError("You don't have permission to view users")
    
    return current_user


async def can_manage_user(
    target_user_id: str,
    current_user: User,
    org_id: str,
    db: AsyncSession
) -> bool:
    """Check if current user can manage the target user.
    
    Prevents:
    - Self-suspension/deactivation
    - Managing users with higher/equal privileges
    """
    # Cannot manage self for sensitive operations
    if target_user_id == current_user.id:
        return False
    
    # TODO: Add role hierarchy check - managers can only manage users
    # with roles lower in the hierarchy
    
    return True


class PermissionChecker:
    """Helper class for checking permissions in service layer."""
    
    def __init__(self, db: AsyncSession, org_id: str, user_id: str):
        self.db = db
        self.org_id = org_id
        self.user_id = user_id
    
    async def has_permission(
        self,
        action: PermissionAction,
        resource_type: RBACResourceType
    ) -> bool:
        """Check if user has a specific permission."""
        from app.enterprise.modules.rbac.schemas import PermissionCheckRequest
        
        result = await rbac_check_permission(
            self.db, self.org_id,
            PermissionCheckRequest(
                user_id=self.user_id,
                action=action,
                resource_type=resource_type
            )
        )
        return result.allowed
    
    async def check_permission(
        self,
        action: PermissionAction,
        resource_type: RBACResourceType
    ) -> None:
        """Check permission and raise ForbiddenError if not allowed."""
        if not await self.has_permission(action, resource_type):
            raise ForbiddenError(
                f"Missing permission: {action.value} on {resource_type.value}"
            )
