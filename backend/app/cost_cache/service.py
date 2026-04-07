"""Cost cache service layer.

Provides functions to get cached data, refresh cache, and manage cache lifecycle.
All CSP API calls are handled in background refresh operations, never blocking
user-facing requests.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cloud_accounts.models import CloudAccount
from app.cloud_accounts.adapters.aws import AWSAdapter
from app.cloud_accounts.adapters.azure import AzureAdapter
from app.cloud_accounts.adapters.gcp import GCPAdapter
from app.config import settings
from app.cost_cache.models import CostCache, CostCacheStatus
from app.cost_cache.schemas import (
    CachedExpenseSummary,
    CachedExpenseBreakdown,
    CacheStatusResponse,
    CacheRefreshResult,
    CloudAccountCostCache,
)
from app.shared.crypto import decrypt
from app.shared.enums import CloudType
from app.shared.utils.time import utc_now
import json

logger = logging.getLogger(__name__)

# In-memory tracking of active refreshes per org
_active_refreshes: dict[str, asyncio.Task] = {}


async def _run_background_refresh(org_id: str) -> None:
    """Run cache refresh in an isolated DB session for background tasks."""
    from app.database import async_session_factory

    async with async_session_factory() as session:
        try:
            await refresh_cost_cache(session, org_id)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.exception(f"Background refresh failed for org {org_id}: {exc}")


def _schedule_background_refresh(org_id: str) -> None:
    """Schedule a background refresh only when one is not already running."""
    refresh_key = f"{org_id}"
    existing_task = _active_refreshes.get(refresh_key)
    if existing_task and not existing_task.done():
        return

    task = asyncio.create_task(_run_background_refresh(org_id))
    _active_refreshes[refresh_key] = task


async def get_cached_summary(
    db: AsyncSession,
    org_id: str,
    allow_stale: bool = True,
) -> CachedExpenseSummary:
    """Get cached expense summary for an organization.
    
    This function never blocks on CSP API calls. It returns cached data
    immediately, or stale data with a warning if cache is expired.
    
    Args:
        db: Database session
        org_id: Organization ID
        allow_stale: If True, return stale data when cache is expired.
                    If False, raise exception when no fresh cache exists.
    
    Returns:
        CachedExpenseSummary with cache metadata
    """
    # Look for non-expired cache entry
    now = utc_now()
    
    result = await db.execute(
        select(CostCache).where(
            CostCache.organization_id == org_id,
            CostCache.cache_type == "summary",
            CostCache.cloud_account_id.is_(None),  # Org-wide summary
            CostCache.expires_at > now,  # Not expired
        )
    )
    cache_entry = result.scalar_one_or_none()
    
    # If we have fresh cache, return it
    if cache_entry:
        logger.debug(f"Cache hit for org {org_id}: summary data age={cache_entry.age_hours():.1f}h")
        return _cache_to_summary_response(cache_entry)
    
    # No fresh cache - check for stale cache if allowed
    if allow_stale:
        result = await db.execute(
            select(CostCache).where(
                CostCache.organization_id == org_id,
                CostCache.cache_type == "summary",
                CostCache.cloud_account_id.is_(None),
            ).order_by(CostCache.collected_at.desc())
        )
        stale_cache = result.scalar_one_or_none()
        
        if stale_cache:
            logger.warning(f"Returning stale cache for org {org_id}: age={stale_cache.age_hours():.1f}h")
            return _cache_to_summary_response(stale_cache, is_stale=True)
    
    # No cache available - trigger background refresh and return zeros
    logger.warning(f"No cache available for org {org_id}, triggering background refresh")

    # Trigger async refresh using an isolated DB session (don't await)
    _schedule_background_refresh(org_id)
    
    return CachedExpenseSummary(
        this_month_total=0.0,
        last_month_total=0.0,
        this_month_forecast=0.0,
        change_percent=0.0,
        data_source="uninitialized",
        cached_at=None,
        expires_at=None,
        cache_age_hours=None,
    )


async def get_cached_breakdown(
    db: AsyncSession,
    org_id: str,
    start_date: str,
    end_date: str,
    group_by: str = "cloud",
    allow_stale: bool = True,
) -> CachedExpenseBreakdown:
    """Get cached expense breakdown for an organization.
    
    Args:
        db: Database session
        org_id: Organization ID
        start_date: Period start (YYYY-MM-DD)
        end_date: Period end (YYYY-MM-DD)
        group_by: How data is grouped ('cloud', 'service', 'region')
        allow_stale: If True, return stale data when cache is expired
    
    Returns:
        CachedExpenseBreakdown with cache metadata
    """
    period_start = datetime.fromisoformat(start_date)
    period_end = datetime.fromisoformat(end_date)
    now = utc_now()
    
    cache_type = f"breakdown_{group_by}"
    
    result = await db.execute(
        select(CostCache).where(
            CostCache.organization_id == org_id,
            CostCache.cache_type == cache_type,
            CostCache.period_start == period_start,
            CostCache.period_end == period_end,
            CostCache.expires_at > now,
        )
    )
    cache_entry = result.scalar_one_or_none()
    
    if cache_entry:
        return _cache_to_breakdown_response(cache_entry)
    
    # No fresh cache - try stale
    if allow_stale:
        result = await db.execute(
            select(CostCache).where(
                CostCache.organization_id == org_id,
                CostCache.cache_type == cache_type,
                CostCache.period_start == period_start,
                CostCache.period_end == period_end,
            ).order_by(CostCache.collected_at.desc())
        )
        stale_cache = result.scalar_one_or_none()
        
        if stale_cache:
            return _cache_to_breakdown_response(stale_cache, is_stale=True)
    
    # No cache available
    logger.warning(f"No breakdown cache for org {org_id}, group_by={group_by}")
    
    return CachedExpenseBreakdown(
        total=0.0,
        previous_total=0.0,
        start_date=start_date,
        end_date=end_date,
        breakdown=[],
        daily_totals=[],
        data_source="uninitialized",
        cached_at=None,
        expires_at=None,
    )


async def refresh_cost_cache(
    db: AsyncSession,
    org_id: str,
    force: bool = False,
) -> CacheRefreshResult:
    """Refresh cost cache for an organization by calling CSP APIs.
    
    This function fetches fresh cost data from all cloud providers and
    stores it in the cache. It handles partial failures gracefully.
    
    Args:
        db: Database session
        org_id: Organization ID
        force: If True, refresh even if cache is not expired
    
    Returns:
        CacheRefreshResult with status and aggregated totals
    """
    logger.info(f"Starting cost cache refresh for org {org_id}")
    
    # Check if already refreshing
    refresh_key = f"{org_id}"
    current_task = asyncio.current_task()
    existing_task = _active_refreshes.get(refresh_key)
    if existing_task and not existing_task.done() and existing_task is not current_task:
        logger.info(f"Refresh already in progress for org {org_id}, skipping")
        return CacheRefreshResult(
            success=True,
            error_message="Refresh already in progress",
        )

    if current_task is not None:
        _active_refreshes[refresh_key] = current_task
    
    try:
        # Get all cloud accounts for this org
        result = await db.execute(
            select(CloudAccount).where(
                CloudAccount.organization_id == org_id,
                CloudAccount.deleted_at.is_(None),
                CloudAccount.type.in_([CloudType.AWS, CloudType.AZURE, CloudType.GCP]),
            )
        )
        accounts = list(result.scalars().all())
        
        if not accounts:
            logger.warning(f"No cloud accounts found for org {org_id}")
            await _update_cache_status(db, org_id, CacheRefreshResult(
                success=True,
                accounts_total=0,
                accounts_success=0,
                accounts_failed=0,
            ))
            return CacheRefreshResult(success=True, accounts_total=0)
        
        # Update status to running
        await _update_cache_status(
            db, org_id,
            CacheRefreshResult(success=True, accounts_total=len(accounts)),
            is_running=True
        )
        
        # Fetch costs for each account in parallel
        account_caches = await _fetch_all_account_costs(db, accounts)
        
        # Aggregate totals
        this_month_total = sum(ac.this_month_total for ac in account_caches)
        last_month_total = sum(ac.last_month_total for ac in account_caches)
        forecast_total = sum(ac.forecast_total for ac in account_caches)
        
        # Calculate change percent
        change_percent = 0.0
        if last_month_total > 0:
            change_percent = round((forecast_total - last_month_total) / last_month_total * 100, 2)
        
        # Store aggregated summary cache
        await _save_summary_cache(
            db, org_id, this_month_total, last_month_total,
            forecast_total, change_percent
        )
        
        # Store individual account caches
        for ac in account_caches:
            await _save_account_cache(db, org_id, ac)
        
        # Count successes/failures
        success_count = sum(1 for ac in account_caches if not ac.error_message)
        failed_count = len(account_caches) - success_count
        
        result = CacheRefreshResult(
            success=failed_count == 0,
            accounts_total=len(accounts),
            accounts_success=success_count,
            accounts_failed=failed_count,
            this_month_total=this_month_total,
            last_month_total=last_month_total,
            forecast_total=forecast_total,
        )
        
        # Update status
        await _update_cache_status(db, org_id, result)
        
        logger.info(
            f"Cost cache refresh complete for org {org_id}: "
            f"{success_count}/{len(accounts)} accounts successful, "
            f"total=${this_month_total:.2f}"
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Failed to refresh cost cache for org {org_id}: {e}")
        error_result = CacheRefreshResult(
            success=False,
            error_message=str(e),
        )
        try:
            await _update_cache_status(db, org_id, error_result)
        except Exception as status_error:
            logger.exception(
                f"Failed to update cache status after refresh error for org {org_id}: {status_error}"
            )
        return error_result
    finally:
        if current_task is not None and _active_refreshes.get(refresh_key) is current_task:
            _active_refreshes.pop(refresh_key, None)


async def get_cache_status(
    db: AsyncSession,
    org_id: str,
) -> CacheStatusResponse:
    """Get cache health status for an organization.
    
    Args:
        db: Database session
        org_id: Organization ID
    
    Returns:
        CacheStatusResponse with health information
    """
    # Get cache status record
    result = await db.execute(
        select(CostCacheStatus).where(
            CostCacheStatus.organization_id == org_id
        )
    )
    status = result.scalar_one_or_none()
    
    if not status:
        return CacheStatusResponse(
            status="uninitialized",
            accounts_cached=0,
            accounts_total=0,
            is_refreshing=False,
        )
    
    # Count current cache entries
    result = await db.execute(
        select(CostCache).where(
            CostCache.organization_id == org_id,
            CostCache.cache_type == "summary",
            CostCache.cloud_account_id.isnot(None),  # Per-account caches
        )
    )
    account_caches = result.scalars().all()
    
    # Check if refresh is running
    refresh_key = f"{org_id}"
    is_refreshing = (
        refresh_key in _active_refreshes 
        and not _active_refreshes[refresh_key].done()
    )
    
    return CacheStatusResponse(
        status=status.get_health_status(),
        last_updated=status.last_successful_collection,
        next_update=status.next_collection_at,
        accounts_cached=len(account_caches),
        accounts_total=status.accounts_total,
        is_refreshing=is_refreshing,
        last_error=status.last_error_message,
    )


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _cache_to_summary_response(
    cache: CostCache,
    is_stale: bool = False,
) -> CachedExpenseSummary:
    """Convert CostCache model to CachedExpenseSummary response."""
    return CachedExpenseSummary(
        this_month_total=float(cache.this_month_total),
        last_month_total=float(cache.last_month_total),
        this_month_forecast=float(cache.forecast_total),
        change_percent=float(cache.change_percent),
        data_source="stale" if is_stale else cache.data_source,
        cached_at=cache.collected_at,
        expires_at=cache.expires_at,
        cache_age_hours=cache.age_hours(),
    )


def _cache_to_breakdown_response(
    cache: CostCache,
    is_stale: bool = False,
) -> CachedExpenseBreakdown:
    """Convert CostCache model to CachedExpenseBreakdown response."""
    breakdown_items = []
    if cache.breakdown_data:
        for item in cache.breakdown_data.get("breakdown", []):
            breakdown_items.append(item)  # Already dict format
    
    return CachedExpenseBreakdown(
        total=float(cache.this_month_total),
        previous_total=float(cache.last_month_total),
        start_date=cache.period_start.isoformat() if cache.period_start else "",
        end_date=cache.period_end.isoformat() if cache.period_end else "",
        breakdown=breakdown_items,
        daily_totals=cache.breakdown_data.get("daily_totals", []) if cache.breakdown_data else [],
        data_source="stale" if is_stale else cache.data_source,
        cached_at=cache.collected_at,
        expires_at=cache.expires_at,
    )


async def _fetch_all_account_costs(
    db: AsyncSession,
    accounts: list[CloudAccount],
) -> list[CloudAccountCostCache]:
    """Fetch cost data from all cloud accounts in parallel."""
    
    async def fetch_single_account(account: CloudAccount) -> CloudAccountCostCache:
        try:
            logger.debug(f"Fetching costs for account {account.id} ({account.name})")
            
            # Decrypt credentials
            config = json.loads(decrypt(account.config))
            
            # Create adapter
            if account.type == CloudType.AWS:
                adapter = AWSAdapter(config)
            elif account.type == CloudType.AZURE:
                adapter = AzureAdapter(config)
            else:  # GCP
                adapter = GCPAdapter(config)
            
            # Fetch cost summary with timeout
            summary = await asyncio.wait_for(
                adapter.get_monthly_cost_summary(),
                timeout=60.0  # 60 seconds per account
            )
            
            return CloudAccountCostCache(
                cloud_account_id=account.id,
                cloud_account_name=account.name,
                cloud_type=account.type.value,
                this_month_total=summary.get("this_month", 0.0),
                last_month_total=summary.get("last_month", 0.0),
                forecast_total=summary.get("forecast", 0.0),
                collected_at=utc_now(),
                expires_at=utc_now() + timedelta(hours=settings.COST_CACHE_TTL_HOURS),
                data_source="live",
                error_message=None,
            )

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching costs for account {account.id}")
            return CloudAccountCostCache(
                cloud_account_id=account.id,
                cloud_account_name=account.name,
                cloud_type=account.type.value,
                collected_at=utc_now(),
                expires_at=utc_now(),  # Already expired
                data_source="error",
                error_message="Timeout fetching costs from cloud provider",
            )
        except Exception as e:
            logger.exception(f"Failed to fetch costs for account {account.id}: {e}")
            return CloudAccountCostCache(
                cloud_account_id=account.id,
                cloud_account_name=account.name,
                cloud_type=account.type.value,
                collected_at=utc_now(),
                expires_at=utc_now(),
                data_source="error",
                error_message=str(e),
            )
    
    # Fetch all accounts in parallel
    tasks = [fetch_single_account(acc) for acc in accounts]
    return await asyncio.gather(*tasks)


async def _save_summary_cache(
    db: AsyncSession,
    org_id: str,
    this_month: float,
    last_month: float,
    forecast: float,
    change_percent: float,
) -> None:
    """Save organization-wide summary cache using UPSERT."""

    now = utc_now()
    period_start = now.replace(day=1)
    period_end = now

    stmt = pg_insert(CostCache).values(
        id=str(uuid4()),
        organization_id=org_id,
        cloud_account_id=None,
        cache_type="summary",
        period_start=period_start,
        period_end=period_end,
        this_month_total=this_month,
        last_month_total=last_month,
        forecast_total=forecast,
        change_percent=change_percent,
        data_source="live",
        collected_at=now,
        expires_at=now + timedelta(hours=settings.COST_CACHE_TTL_HOURS),
    )

    conflict_columns = [
        "organization_id", "cache_type", "cloud_account_id",
        "period_start", "period_end",
    ]

    update_dict = {
        "this_month_total": this_month,
        "last_month_total": last_month,
        "forecast_total": forecast,
        "change_percent": change_percent,
        "data_source": "live",
        "collected_at": now,
        "expires_at": now + timedelta(hours=settings.COST_CACHE_TTL_HOURS),
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_columns,
        set_=update_dict,
    )

    await db.execute(stmt)
    await db.flush()


async def _save_account_cache(
    db: AsyncSession,
    org_id: str,
    account_cache: CloudAccountCostCache,
) -> None:
    """Save per-account cache entry using UPSERT."""

    now = utc_now()
    period_start = now.replace(day=1)
    period_end = now

    stmt = pg_insert(CostCache).values(
        id=str(uuid4()),
        organization_id=org_id,
        cloud_account_id=account_cache.cloud_account_id,
        cache_type="summary",
        period_start=period_start,
        period_end=period_end,
        this_month_total=account_cache.this_month_total,
        last_month_total=account_cache.last_month_total,
        forecast_total=account_cache.forecast_total,
        change_percent=0,
        data_source=account_cache.data_source,
        collected_at=account_cache.collected_at,
        expires_at=account_cache.expires_at,
    )

    conflict_columns = [
        "organization_id", "cache_type", "cloud_account_id",
        "period_start", "period_end",
    ]

    update_dict = {
        "this_month_total": account_cache.this_month_total,
        "last_month_total": account_cache.last_month_total,
        "forecast_total": account_cache.forecast_total,
        "change_percent": 0,
        "data_source": account_cache.data_source,
        "collected_at": account_cache.collected_at,
        "expires_at": account_cache.expires_at,
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_columns,
        set_=update_dict,
    )

    await db.execute(stmt)
    await db.flush()


async def _update_cache_status(
    db: AsyncSession,
    org_id: str,
    result: CacheRefreshResult,
    is_running: bool = False,
) -> None:
    """Update the cache status record."""
    
    query_result = await db.execute(
        select(CostCacheStatus).where(
            CostCacheStatus.organization_id == org_id
        )
    )
    status = query_result.scalar_one_or_none()
    
    from uuid import uuid4
    if not status:
        status = CostCacheStatus(
            id=str(uuid4()),
            organization_id=org_id,
        )
        db.add(status)
    
    if result.success and not is_running:
        status.last_successful_collection = utc_now()
        if result.accounts_failed == 0:
            status.last_collection_status = "success"
        else:
            status.last_collection_status = "partial"
    elif not result.success:
        status.last_collection_status = "failed"
        status.last_error_message = result.error_message
    
    status.accounts_total = result.accounts_total
    status.accounts_success = result.accounts_success
    status.accounts_failed = result.accounts_failed
    
    # Schedule next collection (6 hours from now)
    if not is_running:
        status.next_collection_at = utc_now() + timedelta(hours=6)
    
    await db.flush()