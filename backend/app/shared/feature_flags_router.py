"""Feature flag management endpoints."""
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.shared.feature_flags import FeatureFlag
from app.shared.exceptions import ForbiddenError, NotFoundError
from app.shared.enums import RolePurpose
from pydantic import BaseModel

router = APIRouter(prefix="/feature-flags", tags=["Feature Flags"])

class FlagUpdate(BaseModel):
    enabled: bool
    rollout_percentage: float = 100.0

class FlagResponse(BaseModel):
    name: str
    enabled: bool
    rollout_percentage: float
    description: str


async def require_manager_role(current_user: User = Depends(get_current_user)):
    """Check if user has MANAGER role for feature flag management."""
    if current_user.role not in (RolePurpose.MANAGER,):
        raise ForbiddenError("Feature flag management requires MANAGER role")
    return current_user


def _to_flag_response(flag: dict) -> FlagResponse:
    return FlagResponse(**flag)


@router.get("/", response_model=list[FlagResponse])
async def list_flags(current_user: User = Depends(get_current_user)):
    """List all feature flags."""
    flags = FeatureFlag.list_flags()
    return [_to_flag_response(f) for f in flags]


@router.get("/{name}", response_model=FlagResponse)
async def get_flag(name: str, current_user: User = Depends(get_current_user)):
    """Get a specific feature flag."""
    flag = FeatureFlag.get_flag(name)
    if not flag:
        raise NotFoundError(f"Feature flag '{name}' not found")
    return _to_flag_response(flag)


@router.patch("/{name}", response_model=FlagResponse)
async def update_flag(
    name: str,
    data: FlagUpdate,
    current_user: User = Depends(require_manager_role),
):
    """Update a feature flag. Requires MANAGER role."""
    FeatureFlag.set_flag(name, data.enabled, data.rollout_percentage)
    flag = FeatureFlag.get_flag(name)
    if not flag:
        raise NotFoundError(f"Feature flag '{name}' not found")
    return _to_flag_response(flag)
