"""Cost cache service layer.

Provides functions to get cached data, refresh cache, and manage cache lifecycle.
All CSP API calls are handled in background refresh operations, never blocking
user-facing requests.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
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
        ).order_by(CostCache.collected_at.desc()).limit(1)
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
            ).order_by(CostCache.collected_at.desc()).limit(1)
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
    now = utc_now()
    
    cache_type = f"breakdown_{group_by}"
    
    # Look for fresh (non-expired) breakdown cache for this group_by
    result = await db.execute(
        select(CostCache).where(
            CostCache.organization_id == org_id,
            CostCache.cache_type == cache_type,
            CostCache.cloud_account_id.is_(None),
            CostCache.expires_at > now,
        ).order_by(CostCache.collected_at.desc())
    )
    cache_entry = result.scalars().first()
    
    if cache_entry:
        logger.debug(f"Breakdown cache hit for org {org_id}, group_by={group_by}")
        return _cache_to_breakdown_response(cache_entry)
    
    # No fresh cache - try stale
    if allow_stale:
        result = await db.execute(
            select(CostCache).where(
                CostCache.organization_id == org_id,
                CostCache.cache_type == cache_type,
                CostCache.cloud_account_id.is_(None),
            ).order_by(CostCache.collected_at.desc())
        )
        stale_cache = result.scalars().first()
        
        if stale_cache:
            logger.warning(f"Returning stale breakdown cache for org {org_id}, group_by={group_by}")
            return _cache_to_breakdown_response(stale_cache, is_stale=True)
    
    # No cache available - trigger background refresh
    logger.warning(f"No breakdown cache for org {org_id}, group_by={group_by}, triggering background refresh")
    _schedule_background_refresh(org_id)
    
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
        account_results = await _fetch_all_account_costs(db, accounts)
        account_caches = [ac for ac, _ in account_results]
        
        # Aggregate totals
        this_month_total = sum(ac.this_month_total for ac in account_caches)
        last_month_total = sum(ac.last_month_total for ac in account_caches)
        forecast_total = sum(ac.forecast_total for ac in account_caches)
        
        # Calculate change percent
        change_percent = 0.0
        if last_month_total > 0:
            change_percent = round((forecast_total - last_month_total) / last_month_total * 100, 2)
        
        # Clean up old duplicate cache rows (keeps only the most recent per type)
        await _cleanup_duplicate_caches(db, org_id)

        # Store aggregated summary cache
        await _save_summary_cache(
            db, org_id, this_month_total, last_month_total,
            forecast_total, change_percent
        )
        
        # Store individual account caches
        for ac in account_caches:
            await _save_account_cache(db, org_id, ac)
        
        # Aggregate daily costs across all accounts and save breakdown caches
        now = utc_now()
        period_start_date = now.date() - timedelta(days=30)
        period_end_date = now.date()
        period_start_dt = datetime.combine(period_start_date, datetime.min.time(), tzinfo=timezone.utc)
        period_end_dt = datetime.combine(period_end_date, datetime.min.time(), tzinfo=timezone.utc)

        # --- Ungrouped daily totals (for cost_trend area chart) ---
        merged_daily: dict[str, float] = {}
        for _, dc in account_results:
            for entry in dc.ungrouped:
                date_key = entry.get("date", "")
                if date_key:
                    merged_daily[date_key] = merged_daily.get(date_key, 0.0) + entry.get("cost", 0.0)

        daily_totals = [
            {"date": d, "cost": round(c, 2)}
            for d, c in sorted(merged_daily.items())
        ] if merged_daily else []

        # --- Helper: aggregate grouped daily costs into breakdown items ---
        def _aggregate_grouped_daily(grouped_key: str) -> list[dict]:
            """Aggregate per-account grouped daily costs into org-wide breakdown items.
            breakdown_items: [{id, name, type, total, previous_total, daily_breakdown: [{date, cost}]}]
            previous_total is estimated proportionally from last_month_total.
            """
            # Map: group_key -> {date -> cost}
            group_daily: dict[str, dict[str, float]] = {}
            group_totals: dict[str, float] = {}
            for _, dc in account_results:
                for entry in getattr(dc, grouped_key, []):
                    gk = entry.get("group_key", "Unknown")
                    date_key = entry.get("date", "")
                    cost = entry.get("cost", 0.0)
                    if date_key:
                        group_daily.setdefault(gk, {})
                        group_daily[gk][date_key] = group_daily[gk].get(date_key, 0.0) + cost
                    group_totals[gk] = group_totals.get(gk, 0.0) + cost

            grand_total = sum(group_totals.values()) or 1.0
            items = []
            for gk, total in sorted(group_totals.items()):
                db_list = [
                    {"date": d, "cost": round(c, 2)}
                    for d, c in sorted(group_daily.get(gk, {}).items())
                ]
                # Estimate previous_total proportionally
                prev_est = round(last_month_total * (total / grand_total), 2) if last_month_total > 0 else 0.0
                items.append({
                    "id": gk,
                    "name": gk,
                    "type": grouped_key.replace("by_", ""),
                    "total": round(total, 2),
                    "previous_total": prev_est,
                    "daily_breakdown": db_list,
                })
            return items

        # --- Cloud breakdown ---
        cloud_breakdown_map: dict[str, float] = {}
        cloud_prev_map: dict[str, float] = {}
        for ac, dc in account_results:
            if not ac.error_message:
                cloud_breakdown_map[ac.cloud_type] = (
                    cloud_breakdown_map.get(ac.cloud_type, 0.0) + ac.this_month_total
                )
                cloud_prev_map[ac.cloud_type] = (
                    cloud_prev_map.get(ac.cloud_type, 0.0) + ac.last_month_total
                )
        # Derive cloud-grouped daily costs from ungrouped daily costs per account
        # (since by_cloud is not a valid CSP API dimension — we use account type instead)
        cloud_daily: dict[str, dict[str, float]] = {}
        for ac, dc in account_results:
            if not ac.error_message:
                ctype = ac.cloud_type
                for entry in dc.ungrouped:
                    date_key = entry.get("date", "")
                    cost = entry.get("cost", 0.0)
                    if date_key:
                        cloud_daily.setdefault(ctype, {})
                        cloud_daily[ctype][date_key] = cloud_daily[ctype].get(date_key, 0.0) + cost

        cloud_items = []
        for ctype, total in sorted(cloud_breakdown_map.items()):
            db_list = [
                {"date": d, "cost": round(c, 2)}
                for d, c in sorted(cloud_daily.get(ctype, {}).items())
            ]
            cloud_items.append({
                "id": ctype,
                "name": ctype.upper(),
                "type": "cloud",
                "total": round(total, 2),
                "previous_total": round(cloud_prev_map.get(ctype, 0.0), 2),
                "daily_breakdown": db_list,
            })

        await _save_breakdown_cache(
            db, org_id, "cloud",
            period_start=period_start_dt, period_end=period_end_dt,
            this_month=this_month_total, last_month=last_month_total,
            daily_totals=daily_totals, breakdown=cloud_items,
        )

        # --- Service breakdown ---
        service_items = _aggregate_grouped_daily("by_service")
        await _save_breakdown_cache(
            db, org_id, "service",
            period_start=period_start_dt, period_end=period_end_dt,
            this_month=this_month_total, last_month=last_month_total,
            daily_totals=daily_totals, breakdown=service_items,
        )

        # --- Region breakdown ---
        region_items = _aggregate_grouped_daily("by_region")
        await _save_breakdown_cache(
            db, org_id, "region",
            period_start=period_start_dt, period_end=period_end_dt,
            this_month=this_month_total, last_month=last_month_total,
            daily_totals=daily_totals, breakdown=region_items,
        )

        # --- Tag breakdown ---
        tag_items = _aggregate_grouped_daily("by_tag")
        await _save_breakdown_cache(
            db, org_id, "tag",
            period_start=period_start_dt, period_end=period_end_dt,
            this_month=this_month_total, last_month=last_month_total,
            daily_totals=daily_totals, breakdown=tag_items,
        )
        
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

async def _cleanup_duplicate_caches(db: AsyncSession, org_id: str) -> None:
    """Remove old duplicate cache rows, keeping only the most recent per type+account.

    This is a one-time cleanup for rows that accumulated due to the previous
    period_end microsecond-precision bug (each refresh created a new row instead
    of upserting because the unique constraint on period_start/period_end never
    matched).
    """
    # Find IDs to keep: the most recent row per (cache_type, cloud_account_id)
    from sqlalchemy import func as sa_func
    subq = (
        select(
            sa_func.max(CostCache.id).label("keep_id"),
        )
        .where(CostCache.organization_id == org_id)
        .group_by(CostCache.cache_type, CostCache.cloud_account_id)
        .subquery()
    )

    # Delete all rows for this org that are NOT in the keep set
    await db.execute(
        delete(CostCache).where(
            CostCache.organization_id == org_id,
            CostCache.id.notin_(select(subq.c.keep_id)),
        )
    )


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


class _AccountDailyCosts:
    """Container for daily cost data grouped by different dimensions."""
    __slots__ = ("ungrouped", "by_cloud", "by_service", "by_region", "by_tag")

    def __init__(
        self,
        ungrouped: list[dict] | None = None,
        by_cloud: list[dict] | None = None,
        by_service: list[dict] | None = None,
        by_region: list[dict] | None = None,
        by_tag: list[dict] | None = None,
    ):
        self.ungrouped = ungrouped or []
        self.by_cloud = by_cloud or []
        self.by_service = by_service or []
        self.by_region = by_region or []
        self.by_tag = by_tag or []


async def _fetch_all_account_costs(
    db: AsyncSession,
    accounts: list[CloudAccount],
) -> list[tuple[CloudAccountCostCache, _AccountDailyCosts]]:
    """Fetch cost data from all cloud accounts in parallel.
    
    Returns list of (CloudAccountCostCache, _AccountDailyCosts) tuples.
    """

    async def _safe_daily(adapter, start: str, end: str, group_by: str | None) -> list[dict]:
        try:
            return await asyncio.wait_for(
                adapter.get_daily_costs(start, end, group_by=group_by),
                timeout=30.0,
            )
        except Exception as err:
            logger.warning(f"Failed to fetch daily costs (group_by={group_by}): {err}")
            return []
    
    async def fetch_single_account(account: CloudAccount) -> tuple[CloudAccountCostCache, _AccountDailyCosts]:
        daily = _AccountDailyCosts()
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

            # Fetch daily costs for the past 30 days in parallel
            # Note: by_cloud is derived from account type at org level (not a CSP API
            # dimension — AWS rejects "CLOUD"). by_tag is not supported as a generic
            # dimension by any CSP (AWS/Azure/GCP all require specific tag/label keys).
            # Reducing from 5 to 3 parallel calls also eases Azure rate-limit pressure.
            end = utc_now().date().isoformat()
            start = (utc_now().date() - timedelta(days=30)).isoformat()
            daily.ungrouped, daily.by_service, daily.by_region = await asyncio.gather(
                _safe_daily(adapter, start, end, None),
                _safe_daily(adapter, start, end, "service"),
                _safe_daily(adapter, start, end, "region"),
            )
            # by_cloud and by_tag remain empty lists (populated at org aggregation level)
            
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
            ), daily

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
            ), daily
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
            ), daily
    
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
    # Normalize to midnight UTC so UPSERT conflict detection works
    # (without this, period_end=now has microsecond precision and never matches)
    period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    period_end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

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
    # Normalize to midnight UTC so UPSERT conflict detection works
    period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    period_end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

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


async def _save_breakdown_cache(
    db: AsyncSession,
    org_id: str,
    group_by: str,
    period_start: datetime,
    period_end: datetime,
    this_month: float,
    last_month: float,
    daily_totals: list[dict],
    breakdown: list[dict],
) -> None:
    """Save breakdown cache entry (e.g. breakdown_cloud) using UPSERT."""

    now = utc_now()
    cache_type = f"breakdown_{group_by}"

    breakdown_data = {
        "daily_totals": daily_totals,
        "breakdown": breakdown,
    }

    stmt = pg_insert(CostCache).values(
        id=str(uuid4()),
        organization_id=org_id,
        cloud_account_id=None,
        cache_type=cache_type,
        period_start=period_start,
        period_end=period_end,
        this_month_total=this_month,
        last_month_total=last_month,
        forecast_total=0,
        change_percent=0,
        breakdown_data=breakdown_data,
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
        "forecast_total": 0,
        "change_percent": 0,
        "breakdown_data": breakdown_data,
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