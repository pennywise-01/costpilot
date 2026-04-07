from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db, get_mongo
from app.enterprise.modules.rbac.dependencies import ensure_org_permission, require_org_permission
from app.organizations.models import Employee
from app.resources.schemas import ResourceDetail, ResourceListResponse
from app.resources.service import get_resource, list_resources
from app.shared.degradation import apply_degradation_headers, get_resources_with_fallback
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member, verify_org_membership

router = APIRouter()


@router.get(
    "/organizations/{org_id}/resources",
    response_model=ResourceListResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.RESOURCE))],
)
async def resources_list(
    org_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    cloud_type: str | None = Query(None),
    region: str | None = Query(None),
    pool_id: str | None = Query(None),
    owner_id: str | None = Query(None),
    member: Employee = Depends(get_current_org_member),
    db=Depends(get_db),
    response: Response = None,
):
    filters = {}
    if cloud_type:
        filters["cloud_type"] = cloud_type
    if region:
        filters["region"] = region
    if pool_id:
        filters["pool_id"] = pool_id
    if owner_id:
        filters["owner_id"] = owner_id

    result, data_source, freshness = await get_resources_with_fallback(
        db, org_id, limit, offset, filters or None
    )

    # Apply degradation headers
    if response is not None:
        apply_degradation_headers(response, data_source, freshness)

    return result


@router.get(
    "/resources/{resource_id}",
    response_model=ResourceDetail,
)
async def resource_detail(
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    mongo_db=Depends(get_mongo),
):
    resource = await get_resource(mongo_db, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    org_id = None
    if hasattr(resource, "organization_id") and resource.organization_id:
        org_id = resource.organization_id
        await verify_org_membership(db, current_user.id, org_id)
    elif isinstance(resource, dict) and resource.get("organization_id"):
        org_id = resource["organization_id"]
        await verify_org_membership(db, current_user.id, org_id)

    if org_id:
        await ensure_org_permission(
            db,
            org_id,
            current_user.id,
            PermissionAction.READ,
            RBACResourceType.RESOURCE,
        )
    return resource
