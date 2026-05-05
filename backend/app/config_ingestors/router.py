"""HTTP API for config snapshots (Tier-2 asset inventory)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config_ingestors.schemas import ResourceConfigSnapshotResponse
from app.config_ingestors.service import (
    collect_config_snapshots_for_org,
    list_snapshots_for_org,
)
from app.database import get_db
from app.enterprise.modules.rbac.dependencies import require_org_permission
from app.organizations.models import Employee
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member

router = APIRouter()


@router.get(
    "/organizations/{org_id}/config-snapshots",
    response_model=list[ResourceConfigSnapshotResponse],
    dependencies=[
        Depends(require_org_permission(PermissionAction.READ, RBACResourceType.RECOMMENDATION))
    ],
)
async def list_config_snapshots_endpoint(
    org_id: str,
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List the most recent config snapshots for an organization."""
    snapshots = await list_snapshots_for_org(
        db, org_id, resource_type=resource_type, limit=limit,
    )
    return [ResourceConfigSnapshotResponse.model_validate(s) for s in snapshots]


@router.post(
    "/organizations/{org_id}/config-snapshots/refresh",
    response_model=dict,
    dependencies=[
        Depends(require_org_permission(PermissionAction.UPDATE, RBACResourceType.RECOMMENDATION))
    ],
)
async def refresh_config_snapshots_endpoint(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an on-demand config snapshot scan for the org's eligible accounts."""
    count = await collect_config_snapshots_for_org(db, org_id)
    return {"persisted": count}
