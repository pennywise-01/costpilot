import asyncio
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

from app.config import settings
from app.database import get_db, get_mongo
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.organizations.models import Employee
from app.cloud_accounts.models import CloudAccount
from app.cloud_accounts.schemas import (
    CloudAccountCreate,
    CloudAccountUpdate,
    CloudAccountResponse,
    CloudAccountListItem,
    CloudAccountDetail,
    PaginatedCloudAccounts,
)
from app.cloud_accounts.iam_policies import build_policy, VALID_TIERS
from app.shared.exceptions import BadRequestError
from app.cloud_accounts.service import (
    create_cloud_account,
    list_cloud_accounts,
    get_cloud_account,
    update_cloud_account,
    delete_cloud_account,
    get_cloud_account_resources,
    get_cloud_account_cost_history,
    get_cloud_account_summary,
    validate_cloud_account_credentials,
)
from app.enterprise.modules.rbac.dependencies import ensure_org_permission, require_org_permission
from app.shared.utils.time import utc_now
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member, verify_org_membership
from app.shared.pagination import PaginatedResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Bounded TTL caches for live cloud account data and permission warnings
_live_data_cache: TTLCache = TTLCache(maxsize=500, ttl=300)  # 5 minutes
_permission_cache: TTLCache = TTLCache(maxsize=500, ttl=3600)  # 1 hour


async def _build_response_with_permissions(cloud_account: CloudAccount) -> dict:
    """Build a cloud account response including permission warnings.

    Fetches permission warnings from cache or validates credentials.
    """
    account_id = cloud_account.id

    # Check permission cache
    if account_id in _permission_cache:
        warnings = _permission_cache[account_id]
        base = CloudAccountResponse.model_validate(cloud_account).model_dump()
        base["permission_warnings"] = warnings
        return base

    # Fetch fresh permission warnings
    try:
        warnings = await validate_cloud_account_credentials(cloud_account)
        _permission_cache[account_id] = warnings
    except Exception as e:
        logger.debug(f"Failed to validate credentials for account {account_id}: {e}")
        warnings = []

    base = CloudAccountResponse.model_validate(cloud_account).model_dump()
    base["permission_warnings"] = warnings
    return base


def _get_cached_live_data(account_id: str) -> dict | None:
    """Get cached live data if not expired."""
    if account_id in _live_data_cache:
        logger.debug(f"Live data cache hit for account {account_id}")
        return _live_data_cache[account_id]
    return None


def _get_stale_cached_live_data(account_id: str) -> dict | None:
    """Get cached live data even if expired.

    Used as a fallback when a forced refresh fails due provider/API issues.
    """
    data = _live_data_cache.get(account_id)
    if not data:
        return None
    return data


def _set_cached_live_data(account_id: str, data: dict) -> None:
    """Cache live data for an account."""
    _live_data_cache[account_id] = data
    logger.debug(f"Cached live data for account {account_id}")


async def _build_cost_fallback_from_history(cloud_account: CloudAccount, resources_count: int) -> dict | None:
    """Build cost summary from current-month daily history as a fallback."""
    today = utc_now().date()
    first_of_month = today.replace(day=1)
    days_elapsed = max((today - first_of_month).days + 1, 1)
    days_in_month = ((first_of_month + timedelta(days=32)).replace(day=1) - first_of_month).days

    daily_history = await get_cloud_account_cost_history(cloud_account, days_elapsed)
    if not daily_history:
        return None

    this_month_cost = round(
        sum(float(item.get("cost", 0) or 0) for item in daily_history),
        2,
    )
    forecast = round((this_month_cost / days_elapsed) * days_in_month, 2)

    return {
        "monthly_cost": this_month_cost,
        "forecast": forecast,
        "last_month_cost": 0.0,
        "resources_count": resources_count,
    }


@router.get("/cloud-accounts/iam-policy")
async def get_iam_policy(
    cloud: str = Query(..., description="Cloud: aws | azure | gcp"),
    tiers: str = Query(
        "billing,advisor",
        description=(
            "Comma-separated data-source tiers to include: billing, "
            "advisor, config. Advisor unlocks Tier-1 built-in rules; "
            "config is forward-compatible with Tier-2."
        ),
    ),
    trust_principal: str | None = Query(
        None,
        description=(
            "AWS only. When supplied, the response also includes a "
            "TrustPolicy doc that allows this principal to sts:AssumeRole "
            "into the customer-created read-only role."
        ),
    ),
    external_id: str | None = Query(
        None,
        description="AWS only. ExternalId to require on sts:AssumeRole.",
    ),
    current_user: User = Depends(get_current_user),
):
    """Return the IAM policy document CostPilot needs on a cloud account.

    The returned document is suitable for paste into the AWS IAM
    console (or equivalent Azure/GCP UI). Used by the onboarding
    wizard's "View required IAM policy" button.
    """
    tier_list = [t.strip() for t in tiers.split(",") if t.strip()]
    invalid = [t for t in tier_list if t not in VALID_TIERS]
    if invalid:
        raise BadRequestError(
            f"Unknown tier(s): {invalid}. Valid: {sorted(VALID_TIERS)}"
        )
    try:
        policy = build_policy(
            cloud=cloud,
            tiers=tier_list,
            trust_principal=trust_principal,
            external_id=external_id,
        )
    except ValueError as e:
        raise BadRequestError(str(e))
    return {
        "cloud": cloud,
        "tiers": tier_list,
        "policy": policy,
    }


@router.post(
    "/organizations/{org_id}/cloud-accounts",
    response_model=CloudAccountResponse,
    status_code=201,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.CLOUD_ACCOUNT))],
)
async def create(
    org_id: str,
    data: CloudAccountCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    cloud_account = await create_cloud_account(db, org_id, data)
    return CloudAccountResponse.model_validate(cloud_account)


@router.get(
    "/organizations/{org_id}/cloud-accounts",
    response_model=PaginatedCloudAccounts,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.CLOUD_ACCOUNT))],
)
async def list_all(
    org_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List all cloud accounts for an organization.

    Returns only database data without making live cloud API calls.
    Use GET /cloud-accounts/{id}/live-data for live data.
    """
    logger.debug(f"list_all called - org_id={org_id}, member_id={member.id}")

    offset = (page - 1) * page_size
    accounts, total = await list_cloud_accounts(db, org_id, offset=offset, limit=page_size)
    logger.debug(f"Found {len(accounts)} cloud accounts for org_id={org_id} (total: {total})")

    # Return only DB data - no live cloud API calls
    results = [
        CloudAccountListItem.model_validate(account)
        for account in accounts
    ]

    logger.debug(f"Returning {len(results)} accounts (DB data only)")
    return PaginatedResponse.create(
        items=results,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/cloud-accounts/{id}",
    response_model=CloudAccountResponse,
)
async def get_one(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single cloud account (DB data only)."""
    cloud_account = await get_cloud_account(db, id)
    await verify_org_membership(db, current_user.id, cloud_account.organization_id)
    await ensure_org_permission(
        db,
        cloud_account.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.CLOUD_ACCOUNT,
    )
    return await _build_response_with_permissions(cloud_account)


@router.get(
    "/cloud-accounts/{id}/live-data",
    response_model=CloudAccountDetail,
)
async def get_live_data(
    id: str,
    force_refresh: bool = Query(False, description="Force refresh from cloud API (bypass cache)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get live data for a specific cloud account.
    
    This endpoint fetches real-time data from the cloud provider API
    including resource counts and cost information. Results are cached
    for 5 minutes to prevent rate limiting.
    
    Use force_refresh=true to bypass cache and fetch fresh data.
    Rate-limited to 10 requests/minute when force_refresh is true.
    """
    # Rate-limit forced refreshes to prevent cloud API abuse
    if force_refresh and settings.RATE_LIMITING_ENABLED:
        from app.shared.rate_limit import check_rate_limit
        await check_rate_limit(
            f"cloud_force_refresh:{current_user.id}",
            max_requests=settings.RATE_LIMIT_EXPENSIVE_REQUESTS,
            window_seconds=60,
        )

    cloud_account = await get_cloud_account(db, id)
    await verify_org_membership(db, current_user.id, cloud_account.organization_id)
    await ensure_org_permission(
        db,
        cloud_account.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.CLOUD_ACCOUNT,
    )
    
    # Check cache first (unless force refresh)
    if not force_refresh:
        cached = _get_cached_live_data(id)
        if cached:
            perms = await _build_response_with_permissions(cloud_account)
            return CloudAccountDetail(
                **perms,
                monthly_cost=cached.get("monthly_cost", 0),
                forecast=cached.get("forecast", 0),
                last_month_cost=cached.get("last_month_cost", 0),
                resources_count=cached.get("resources_count", 0),
                data_source="cache",
                cached_at=utc_now(),
            )

    # Fetch live data from cloud provider
    logger.info(f"Fetching live data for account {id} ({cloud_account.name})")
    
    try:
        summary = await asyncio.wait_for(
            get_cloud_account_summary(cloud_account),
            timeout=settings.CLOUD_ACCOUNT_LIVE_DATA_TIMEOUT
        )

        # If provider cost fetch failed, keep returning stale cache instead of overwriting with zeros.
        if not summary.get("cost_data_available", True):
            try:
                history_fallback = await _build_cost_fallback_from_history(
                    cloud_account,
                    summary.get("resources_count", 0),
                )
                if history_fallback:
                    logger.warning(
                        "Cloud account monthly summary unavailable for %s; using daily history fallback",
                        id,
                    )
                    _set_cached_live_data(id, history_fallback)
                    perms = await _build_response_with_permissions(cloud_account)
                    return CloudAccountDetail(
                        **perms,
                        monthly_cost=history_fallback.get("monthly_cost", 0),
                        forecast=history_fallback.get("forecast", 0),
                        last_month_cost=history_fallback.get("last_month_cost", 0),
                        resources_count=history_fallback.get("resources_count", 0),
                        data_source="live",
                        cached_at=utc_now(),
                    )
            except Exception as history_error:
                logger.warning(
                    "Failed to build daily-history fallback for %s: %s",
                    id,
                    history_error,
                )

            stale_cached = _get_stale_cached_live_data(id)
            if stale_cached:
                logger.warning(
                    "Cloud account live data refresh failed for %s; returning stale cached values",
                    id,
                )
                perms = await _build_response_with_permissions(cloud_account)
                return CloudAccountDetail(
                    **perms,
                    monthly_cost=stale_cached.get("monthly_cost", 0),
                    forecast=stale_cached.get("forecast", 0),
                    last_month_cost=stale_cached.get("last_month_cost", 0),
                    resources_count=stale_cached.get("resources_count", 0),
                    data_source="cache",
                    cached_at=utc_now(),
                )

            logger.warning(
                "Cloud account live data unavailable for %s and no cached fallback exists",
                id,
            )
            perms = await _build_response_with_permissions(cloud_account)
            return CloudAccountDetail(
                **perms,
                monthly_cost=0,
                forecast=0,
                last_month_cost=0,
                resources_count=summary.get("resources_count", 0),
                data_source="unavailable",
                cached_at=None,
            )
        
        # Cache the result
        _set_cached_live_data(id, summary)

        perms = await _build_response_with_permissions(cloud_account)
        return CloudAccountDetail(
            **perms,
            monthly_cost=summary.get("monthly_cost", 0),
            forecast=summary.get("forecast", 0),
            last_month_cost=summary.get("last_month_cost", 0),
            resources_count=summary.get("resources_count", 0),
            data_source="live",
            cached_at=utc_now(),
        )

    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching live data for account {id}")
        perms = await _build_response_with_permissions(cloud_account)
        return CloudAccountDetail(
            **perms,
            monthly_cost=0,
            forecast=0,
            last_month_cost=0,
            resources_count=0,
            data_source="unavailable",
            cached_at=None,
        )
    except Exception as e:
        logger.warning(f"Error fetching live data for account {id}: {e}")
        perms = await _build_response_with_permissions(cloud_account)
        return CloudAccountDetail(
            **perms,
            monthly_cost=0,
            forecast=0,
            last_month_cost=0,
            resources_count=0,
            data_source="unavailable",
            cached_at=None,
        )


@router.patch(
    "/cloud-accounts/{id}",
    response_model=CloudAccountResponse,
)
async def update(
    id: str,
    data: CloudAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cloud_account = await get_cloud_account(db, id)
    await verify_org_membership(db, current_user.id, cloud_account.organization_id)
    await ensure_org_permission(
        db,
        cloud_account.organization_id,
        current_user.id,
        PermissionAction.UPDATE,
        RBACResourceType.CLOUD_ACCOUNT,
    )
    cloud_account = await update_cloud_account(db, id, data)

    # Invalidate cache when account is updated
    _live_data_cache.pop(id, None)
    _permission_cache.pop(id, None)

    return await _build_response_with_permissions(cloud_account)


@router.delete("/cloud-accounts/{id}", status_code=204)
async def delete(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cloud_account = await get_cloud_account(db, id)
    await verify_org_membership(db, current_user.id, cloud_account.organization_id)
    await ensure_org_permission(
        db,
        cloud_account.organization_id,
        current_user.id,
        PermissionAction.DELETE,
        RBACResourceType.CLOUD_ACCOUNT,
    )
    await delete_cloud_account(db, id)

    # Invalidate cache when account is deleted
    _live_data_cache.pop(id, None)
    _permission_cache.pop(id, None)


@router.get("/cloud-accounts/{id}/resources")
async def get_resources(
    id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get resources for a specific cloud account.
    
    This fetches live resource data from the cloud provider.
    Consider using the cached /live-data endpoint for frequent polling.
    """
    cloud_account = await get_cloud_account(db, id)
    await verify_org_membership(db, current_user.id, cloud_account.organization_id)
    await ensure_org_permission(
        db,
        cloud_account.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.CLOUD_ACCOUNT,
    )
    resources = await get_cloud_account_resources(cloud_account, limit)
    return resources


@router.get("/cloud-accounts/{id}/cost-history")
async def get_cost_history(
    id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily cost history for a specific cloud account.
    
    This fetches live cost data from the cloud provider.
    Consider using the cached /live-data endpoint for frequent polling.
    """
    cloud_account = await get_cloud_account(db, id)
    await verify_org_membership(db, current_user.id, cloud_account.organization_id)
    await ensure_org_permission(
        db,
        cloud_account.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.CLOUD_ACCOUNT,
    )
    cost_history = await get_cloud_account_cost_history(cloud_account, days)
    return cost_history
