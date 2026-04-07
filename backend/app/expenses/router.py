from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cost_cache.schemas import (
    CachedExpenseSummary,
    CachedExpenseBreakdown,
    CacheStatusResponse,
    CacheRefreshRequest,
    CacheRefreshResponse,
)
from app.cost_cache.service import (
    get_cached_summary,
    get_cached_breakdown,
    get_cache_status,
    refresh_cost_cache,
)
from app.database import get_db, get_mongo, get_mongo_db
from app.expenses.schemas import CleanExpense, ExpenseBreakdown, ExpenseSummary
from app.expenses.service import (
    get_clean_expenses,
    get_expense_breakdown,
    get_expense_summary,
)
from app.enterprise.modules.rbac.dependencies import require_org_permission
from app.organizations.models import Employee
from app.shared.degradation import (
    apply_degradation_headers,
    get_expenses_with_fallback,
)
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member

router = APIRouter()


@router.get(
    "/organizations/{org_id}/expenses/summary",
    response_model=CachedExpenseSummary,
    summary="Get expense summary (cached)",
    description="Returns cached expense summary for fast dashboard loads. Uses persisted cache data instead of live CSP API calls.",
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.EXPENSE))],
)
async def expense_summary(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
    allow_stale: bool = Query(True, description="Return stale cache if no fresh data available"),
    response: Response = None,
):
    """Get expense summary with graceful degradation.

    Attempts live data first, falls back to cache, then returns degraded response.
    Response headers indicate data source and freshness.
    """
    result, data_source, freshness = await get_expenses_with_fallback(
        db, org_id, start_date=None, end_date=None, allow_stale=allow_stale
    )

    # Apply degradation headers
    if response is not None:
        apply_degradation_headers(response, data_source, freshness)

    # If result is already a CachedExpenseSummary, return as-is
    if hasattr(result, "model_dump") and hasattr(result, "data_source"):
        return result

    # Convert ExpenseSummary to CachedExpenseSummary
    return CachedExpenseSummary(
        this_month_total=result.this_month_total,
        last_month_total=result.last_month_total,
        this_month_forecast=result.this_month_forecast,
        change_percent=result.change_percent,
        data_source=data_source,
        cached_at=None,
        expires_at=None,
        cache_age_hours=None,
    )


@router.get(
    "/organizations/{org_id}/expenses/breakdown",
    response_model=CachedExpenseBreakdown,
    summary="Get expense breakdown (cached)",
    description="Returns cached expense breakdown by cloud, service, or region.",
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.EXPENSE))],
)
async def expense_breakdown(
    org_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    group_by: str = Query("cloud", description="Group by: cloud, service, or region"),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
    allow_stale: bool = Query(True, description="Return stale cache if no fresh data available"),
    response: Response = None,
):
    """Get expense breakdown with graceful degradation.

    Attempts live data first, falls back to cache, then returns degraded response.
    """
    result, data_source, freshness = await get_expenses_with_fallback(
        db, org_id, start_date=start_date, end_date=end_date, group_by=group_by, allow_stale=allow_stale
    )

    # Apply degradation headers
    if response is not None:
        apply_degradation_headers(response, data_source, freshness)

    # If result is already a CachedExpenseBreakdown, return as-is
    if hasattr(result, "model_dump") and hasattr(result, "data_source"):
        return result

    # Convert ExpenseBreakdown to CachedExpenseBreakdown
    return CachedExpenseBreakdown(
        total=result.total,
        previous_total=result.previous_total,
        start_date=result.start_date,
        end_date=result.end_date,
        breakdown=[item.model_dump() for item in result.breakdown],
        daily_totals=[item.model_dump() for item in result.daily_totals],
        data_source=data_source,
        cached_at=None,
        expires_at=None,
    )


@router.get(
    "/organizations/{org_id}/expenses/cache-status",
    response_model=CacheStatusResponse,
    summary="Get cost cache status",
    description="Returns the health status of the cost cache for this organization.",
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.EXPENSE))],
)
async def expense_cache_status(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get cache health status.
    
    Returns information about:
    - When cache was last updated
    - How many accounts have cached data
    - Whether a refresh is in progress
    - Any errors from last refresh
    """
    return await get_cache_status(db, org_id)


@router.post(
    "/organizations/{org_id}/expenses/refresh",
    response_model=CacheRefreshResponse,
    summary="Refresh cost cache",
    description="Manually trigger a refresh of the cost cache. This fetches fresh data from all CSPs.",
    dependencies=[Depends(require_org_permission(PermissionAction.MANAGE, RBACResourceType.EXPENSE))],
)
async def refresh_expense_cache(
    org_id: str,
    request: CacheRefreshRequest,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Manually refresh cost cache.
    
    This triggers a background job to fetch fresh cost data from all cloud providers.
    The refresh happens asynchronously - this endpoint returns immediately.
    
    Use this when:
    - Cache is stale and you need fresh data
    - New cloud account was just added
    - Troubleshooting cache issues
    """
    from datetime import timedelta

    from app.shared.utils.time import utc_now

    # Trigger async refresh
    result = await refresh_cost_cache(db, org_id, force=request.force)
    
    if result.error_message and "already in progress" in result.error_message:
        return CacheRefreshResponse(
            status="skipped",
            message="A refresh is already in progress. Please wait for it to complete.",
            estimated_completion=None,
        )
    
    return CacheRefreshResponse(
        status="refreshing",
        message=f"Cost cache refresh started for {result.accounts_total} accounts",
        estimated_completion=utc_now() + timedelta(minutes=5),
    )


@router.get(
    "/organizations/{org_id}/expenses/clean",
    response_model=list[CleanExpense],
    summary="Get clean expense line items",
    description="Returns expense line items from CSP APIs. This endpoint always fetches live data.",
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.EXPENSE))],
)
async def clean_expenses(
    org_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    member: Employee = Depends(get_current_org_member),
    mongo_db=Depends(get_mongo),
):
    """Get clean expense line items.
    
    This endpoint returns individual expense line items.
    Note: This always fetches live data from CSPs (not cached).
    """
    return await get_clean_expenses(mongo_db, org_id, limit, offset)


# Legacy endpoints for backward compatibility (when cache is disabled)
@router.get(
    "/organizations/{org_id}/expenses/summary/live",
    response_model=ExpenseSummary,
    summary="Get live expense summary",
    description="Fetches fresh expense summary directly from CSP APIs. May be slow.",
    deprecated=True,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.EXPENSE))],
)
async def expense_summary_live(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    mongo_db=Depends(get_mongo),
):
    """Get live expense summary (deprecated).
    
    This endpoint fetches fresh data from CSP APIs and may be slow.
    Use /expenses/summary for cached data.
    """
    return await get_expense_summary(mongo_db, org_id)
