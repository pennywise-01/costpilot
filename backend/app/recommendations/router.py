from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_mongo
from app.enterprise.modules.rbac.dependencies import require_org_permission
from app.organizations.models import Employee
from app.recommendations.csp_service import clear_recommendations_cache
from app.recommendations.schemas import RecommendationType, RecommendationsOverview
from app.recommendations.service import (
    dismiss_recommendation,
    get_recommendation_by_type,
    get_recommendations_overview,
)
from app.shared.degradation import apply_degradation_headers, get_recommendations_with_fallback
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member

router = APIRouter()


@router.get(
    "/organizations/{org_id}/recommendations",
    response_model=RecommendationsOverview,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.RECOMMENDATION))],
)
async def recommendations_overview(
    org_id: str,
    cloud_account_id: Optional[list[str]] = Query(None),
    member: Employee = Depends(get_current_org_member),
    mongo_db=Depends(get_mongo),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    result, data_source, freshness = await get_recommendations_with_fallback(
        db, org_id, cloud_account_id
    )

    # Apply degradation headers
    if response is not None:
        apply_degradation_headers(response, data_source, freshness)

    return result


@router.get(
    "/organizations/{org_id}/recommendations/{rec_type}",
    response_model=RecommendationType,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.RECOMMENDATION))],
)
async def recommendation_detail(
    org_id: str,
    rec_type: str,
    member: Employee = Depends(get_current_org_member),
    mongo_db=Depends(get_mongo),
    db: AsyncSession = Depends(get_db),
):
    rec = await get_recommendation_by_type(mongo_db, org_id, rec_type, db=db)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation type not found")
    return rec


@router.patch(
    "/organizations/{org_id}/recommendations/{rec_id}/dismiss",
    dependencies=[Depends(require_org_permission(PermissionAction.MANAGE, RBACResourceType.RECOMMENDATION))],
)
async def dismiss_rec(
    org_id: str,
    rec_id: str,
    member: Employee = Depends(get_current_org_member),
    mongo_db=Depends(get_mongo),
):
    result = await dismiss_recommendation(mongo_db, org_id, rec_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail="Recommendation item not found")
    return result


@router.post(
    "/organizations/{org_id}/recommendations/clear-cache",
    dependencies=[Depends(require_org_permission(PermissionAction.MANAGE, RBACResourceType.RECOMMENDATION))],
)
async def clear_cache(
    org_id: str,
    cloud_account_id: Optional[str] = None,
    member: Employee = Depends(get_current_org_member),
    mongo_db=Depends(get_mongo),
):
    """Clear the CSP recommendations cache.
    
    Call this endpoint to force a fresh fetch from Azure/AWS/GCP APIs.
    Useful when recommendations are suppressed in the cloud portal but still showing in CostPilot.
    """
    deleted_count = await clear_recommendations_cache(mongo_db, cloud_account_id)
    return {
        "message": "Cache cleared successfully",
        "deleted_entries": deleted_count,
        "cloud_account_id": cloud_account_id or "all",
    }
