"""Expenses service - Fetches real cost data from connected cloud accounts."""

import json
import logging
from collections import defaultdict
from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cloud_accounts.adapters.aws import AWSAdapter
from app.cloud_accounts.adapters.azure import AzureAdapter
from app.cloud_accounts.adapters.gcp import GCPAdapter
from app.cloud_accounts.models import CloudAccount
from app.config import settings
from app.expenses.schemas import (
    BreakdownItem,
    CleanExpense,
    DailyExpense,
    ExpenseBreakdown,
    ExpenseSummary,
    PartialFailure,
)
from app.shared.crypto import decrypt
from app.shared.enums import CloudType
from app.shared.request_coalescing import coalesce_cloud_costs
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)

# In-memory cache for expense data (org_id -> (data, timestamp))
_expense_cache: dict[str, tuple[dict, float]] = {}


def _get_cache_key(org_id: str, operation: str, **params) -> str:
    """Generate cache key for expense operations."""
    param_str = ":".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"expense:{org_id}:{operation}:{param_str}"


def _get_cached_expense_data(org_id: str, operation: str, **params) -> dict | None:
    """Get cached expense data if not expired."""
    if not settings.CLOUD_CACHE_ENABLED:
        return None
    
    cache_key = _get_cache_key(org_id, operation, **params)
    if cache_key in _expense_cache:
        data, timestamp = _expense_cache[cache_key]
        ttl = settings.CACHE_TTL_EXPENSE_SUMMARY if operation == "summary" else settings.CACHE_TTL_EXPENSE_BREAKDOWN
        if utc_now().timestamp() - timestamp < ttl:
            logger.debug(f"Expense cache hit: {cache_key}")
            return data
        # Expired, remove it
        del _expense_cache[cache_key]
    return None


def _set_cached_expense_data(org_id: str, operation: str, data: dict, **params) -> None:
    """Cache expense data."""
    if not settings.CLOUD_CACHE_ENABLED:
        return
    
    cache_key = _get_cache_key(org_id, operation, **params)
    _expense_cache[cache_key] = (data, utc_now().timestamp())
    logger.debug(f"Cached expense data: {cache_key}")


async def _get_cloud_adapters(db: AsyncSession, org_id: str) -> list[tuple[CloudAccount, AWSAdapter | AzureAdapter]]:
    """Get cloud adapters for all supported cloud accounts in the organization."""
    from app.database import async_session_factory
    
    logger.info(f"[DEBUG] Fetching cloud accounts for org_id: {org_id}")
    
    async with async_session_factory() as session:
        result = await session.execute(
            select(CloudAccount).where(
                CloudAccount.organization_id == org_id,
                CloudAccount.deleted_at.is_(None),
                CloudAccount.type.in_([CloudType.AWS, CloudType.AZURE, CloudType.GCP]),
            )
        )
        accounts = list(result.scalars().all())
    
    logger.info(f"[DEBUG] Found {len(accounts)} cloud accounts in database for org {org_id}")
    for acc in accounts:
        logger.info(f"[DEBUG] Account: {acc.name}, type: {acc.type}, id: {acc.id}")
    
    adapters = []
    for account in accounts:
        try:
            logger.info(f"[DEBUG] Initializing adapter for account: {account.name} (type: {account.type})")
            config = json.loads(decrypt(account.config))
            logger.info(f"[DEBUG] Decrypted config keys: {list(config.keys())}")
            
            if account.type == CloudType.AWS:
                adapter = AWSAdapter(config)
            elif account.type == CloudType.AZURE:
                adapter = AzureAdapter(config)
            elif account.type == CloudType.GCP:
                adapter = GCPAdapter(config)
            else:
                logger.warning(f"[DEBUG] Unsupported cloud type: {account.type}")
                continue
            adapters.append((account, adapter))
            logger.info(f"[DEBUG] Successfully created adapter for {account.name}")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to create adapter for account {account.name}: {e}", exc_info=True)
            continue
    
    logger.info(f"[DEBUG] Returning {len(adapters)} valid adapters")
    return adapters


async def _fetch_cost_summary_with_coalescing(
    adapters: list[tuple[CloudAccount, AWSAdapter | AzureAdapter | GCPAdapter]]
) -> tuple[float, float, float]:
    """Fetch cost summary from all adapters with request coalescing.
    
    This coalesces identical cost queries to prevent duplicate API calls
    when multiple concurrent users are requesting the same data.
    Each account has a per-account timeout to prevent one slow account
    from blocking all others.
    """
    import asyncio
    
    this_month_total = 0.0
    last_month_total = 0.0
    forecast_total = 0.0
    
    logger.info(f"[DEBUG] Fetching cost summary from {len(adapters)} adapters")
    
    async def fetch_single_account(account: CloudAccount, adapter) -> dict | None:
        """Fetch cost summary for a single account with timeout."""
        try:
            logger.info(f"[DEBUG] Calling get_monthly_cost_summary for account: {account.name} (type: {account.type})")
            # Use coalescing for expensive cost API calls with per-account timeout
            summary = await asyncio.wait_for(
                coalesce_cloud_costs(adapter.get_monthly_cost_summary),
                timeout=20.0  # 20 seconds per account max
            )
            logger.info(f"[DEBUG] Cost summary for {account.name}: this_month={summary.get('this_month')}, last_month={summary.get('last_month')}, forecast={summary.get('forecast')}")
            return summary
        except asyncio.TimeoutError:
            logger.warning(f"[DEBUG] Timeout fetching cost summary for account {account.name}")
            return None
        except Exception as e:
            logger.error(f"[DEBUG] Error fetching costs for account {account.name}: {e}", exc_info=True)
            return None
    
    # Fetch all accounts in parallel with individual timeouts
    tasks = [
        fetch_single_account(account, adapter)
        for account, adapter in adapters
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, dict):
            this_month_total += result.get("this_month", 0)
            last_month_total += result.get("last_month", 0)
            forecast_total += result.get("forecast", 0)
        elif isinstance(result, Exception):
            logger.error(f"Unexpected error fetching cost summary: {result}")
    
    return this_month_total, last_month_total, forecast_total


async def get_expense_summary(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
) -> ExpenseSummary:
    """Return high-level expense summary aggregated from all cloud accounts.
    
    Uses caching and request coalescing to handle concurrent users efficiently.
    """
    # Check cache first
    cached = _get_cached_expense_data(org_id, "summary")
    if cached:
        return ExpenseSummary(**cached)
    
    from app.database import async_session_factory
    
    async with async_session_factory() as db:
        adapters = await _get_cloud_adapters(db, org_id)
    
    logger.info(f"Found {len(adapters)} cloud accounts for org {org_id}")
    
    # Fetch costs with coalescing
    this_month_total, last_month_total, forecast_total = await _fetch_cost_summary_with_coalescing(adapters)
    
    change_percent = 0.0
    if last_month_total > 0:
        change_percent = round((forecast_total - last_month_total) / last_month_total * 100, 2)
    
    result = ExpenseSummary(
        this_month_total=round(this_month_total, 2),
        last_month_total=round(last_month_total, 2),
        this_month_forecast=round(forecast_total, 2),
        change_percent=change_percent,
    )
    
    # Cache the result
    _set_cached_expense_data(org_id, "summary", result.model_dump())
    
    return result


async def get_expense_breakdown(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
    start_date: str,
    end_date: str,
    group_by: str = "cloud",
) -> ExpenseBreakdown:
    """Return expense breakdown grouped by cloud account or service.
    
    Uses caching and request coalescing for efficient concurrent access.
    """
    # Check cache first
    cached = _get_cached_expense_data(org_id, "breakdown", start_date=start_date, end_date=end_date, group_by=group_by)
    if cached:
        return ExpenseBreakdown(**cached)
    
    from app.database import async_session_factory
    
    async with async_session_factory() as db:
        adapters = await _get_cloud_adapters(db, org_id)
    
    # Map group_by to dimension (works for both AWS and Azure)
    aws_dimension = {
        "cloud": None,  # Group by cloud account (we handle this ourselves)
        "service": "SERVICE",
        "region": "REGION",
    }.get(group_by, None)
    
    breakdown_items: list[BreakdownItem] = []
    daily_totals_map: dict[str, float] = defaultdict(float)
    grand_total = 0.0
    partial_failures: list[PartialFailure] = []

    # Adjust end_date for AWS API (exclusive)
    end_dt = datetime.fromisoformat(end_date).date() + timedelta(days=1)
    adjusted_end = end_dt.isoformat()

    if group_by == "cloud":
        # Group by cloud account
        for account, adapter in adapters:
            try:
                # Use coalescing for expensive cost API calls
                daily_costs = await coalesce_cloud_costs(
                    adapter.get_daily_costs,
                    start_date,
                    adjusted_end
                )

                account_total = sum(d["cost"] for d in daily_costs)
                grand_total += account_total

                daily_breakdown = []
                for d in daily_costs:
                    daily_breakdown.append(DailyExpense(date=d["date"], cost=d["cost"]))
                    daily_totals_map[d["date"]] += d["cost"]

                breakdown_items.append(BreakdownItem(
                    id=account.id,
                    name=account.name,
                    type="cloud",
                    total=round(account_total, 2),
                    previous_total=0,  # Would need another API call
                    daily_breakdown=daily_breakdown,
                ))
            except Exception as e:
                logger.error(f"Failed to fetch costs for account {account.id}: {e}")
                partial_failures.append(PartialFailure(
                    account_id=account.id,
                    account_name=account.name,
                    cloud_type=account.type.value,
                    error=str(e)[:200],
                ))
    else:
        # Group by SERVICE or REGION across all accounts
        grouped_data: dict[str, list[dict]] = defaultdict(list)

        for account, adapter in adapters:
            try:
                # Use coalescing for expensive cost API calls
                daily_costs = await coalesce_cloud_costs(
                    adapter.get_daily_costs,
                    start_date,
                    adjusted_end,
                    group_by=aws_dimension
                )
                for d in daily_costs:
                    group_key = d.get("group_key", "Unknown")
                    grouped_data[group_key].append(d)
            except Exception as e:
                logger.error(f"Failed to fetch costs for account {account.id}: {e}")
                partial_failures.append(PartialFailure(
                    account_id=account.id,
                    account_name=account.name,
                    cloud_type=account.type.value,
                    error=str(e)[:200],
                ))
        
        for group_key, costs in grouped_data.items():
            group_total = sum(d["cost"] for d in costs)
            grand_total += group_total
            
            # Aggregate daily costs for this group
            daily_by_date: dict[str, float] = defaultdict(float)
            for d in costs:
                daily_by_date[d["date"]] += d["cost"]
                daily_totals_map[d["date"]] += d["cost"]
            
            daily_breakdown = [
                DailyExpense(date=date, cost=round(cost, 2))
                for date, cost in sorted(daily_by_date.items())
            ]
            
            breakdown_items.append(BreakdownItem(
                id=group_key,
                name=group_key,
                type=group_by,
                total=round(group_total, 2),
                previous_total=0,
                daily_breakdown=daily_breakdown,
            ))
    
    # Sort breakdown by total cost descending
    breakdown_items.sort(key=lambda x: x.total, reverse=True)

    daily_totals = [
        DailyExpense(date=date, cost=round(cost, 2))
        for date, cost in sorted(daily_totals_map.items())
    ]

    has_errors = len(partial_failures) > 0
    if has_errors and len(adapters) > 0 and len(partial_failures) > len(adapters) / 2:
        logger.warning(
            f"Majority of accounts failed during expense breakdown: "
            f"{len(partial_failures)}/{len(adapters)} accounts failed"
        )

    result = ExpenseBreakdown(
        total=round(grand_total, 2),
        previous_total=0,
        start_date=start_date,
        end_date=end_date,
        breakdown=breakdown_items,
        daily_totals=daily_totals,
        partial_failures=partial_failures,
        has_errors=has_errors,
    )
    
    # Cache the result
    _set_cached_expense_data(org_id, "breakdown", result.model_dump(), start_date=start_date, end_date=end_date, group_by=group_by)
    
    return result


async def get_clean_expenses(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[CleanExpense]:
    """Return expense line items from Cost Explorer grouped by service."""
    # Check cache first
    cache_key = f"clean_expenses:{org_id}:{limit}:{offset}"
    if cache_key in _expense_cache:
        data, timestamp = _expense_cache[cache_key]
        if utc_now().timestamp() - timestamp < settings.CACHE_TTL_EXPENSE_BREAKDOWN:
            return [CleanExpense(**item) for item in data]
        del _expense_cache[cache_key]

    from app.database import async_session_factory

    async with async_session_factory() as db:
        adapters = await _get_cloud_adapters(db, org_id)

    # Get last 30 days of costs grouped by service
    end_date = utc_now().date()
    start_date = end_date - timedelta(days=30)

    expenses: list[CleanExpense] = []
    partial_failures: list[PartialFailure] = []

    for account, adapter in adapters:
        try:
            # Use coalescing for expensive cost API calls
            daily_costs = await coalesce_cloud_costs(
                adapter.get_daily_costs,
                start_date.isoformat(),
                (end_date + timedelta(days=1)).isoformat(),
                group_by="SERVICE",
            )

            # Aggregate by service
            service_totals: dict[str, float] = defaultdict(float)
            for d in daily_costs:
                service = d.get("group_key", "Unknown")
                service_totals[service] += d["cost"]

            # Determine cloud type and resource type label
            if account.type == CloudType.AWS:
                cloud_type_str = "aws_cnr"
                resource_type_label = "AWS Service"
            elif account.type == CloudType.AZURE:
                cloud_type_str = "azure_cnr"
                resource_type_label = "Azure Service"
            else:  # GCP
                cloud_type_str = "gcp_cnr"
                resource_type_label = "GCP Service"

            for service, cost in service_totals.items():
                if cost > 0.01:  # Filter out near-zero costs
                    expenses.append(CleanExpense(
                        resource_id=f"{account.id}:{service}",
                        resource_name=service,
                        resource_type=resource_type_label,
                        cloud_account_id=account.id,
                        cloud_account_name=account.name,
                        cloud_type=cloud_type_str,
                        region="global",
                        owner_name=None,
                        pool_name=None,
                        cost=round(cost, 2),
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch costs for account {account.id}: {e}")
            partial_failures.append(PartialFailure(
                account_id=account.id,
                account_name=account.name,
                cloud_type=account.type.value,
                error=str(e)[:200],
            ))
    
    # Sort by cost descending and paginate
    expenses.sort(key=lambda x: x.cost, reverse=True)
    result = expenses[offset:offset + limit]

    if partial_failures and len(adapters) > 0 and len(partial_failures) > len(adapters) / 2:
        logger.warning(
            f"Majority of accounts failed during clean expenses fetch: "
            f"{len(partial_failures)}/{len(adapters)} accounts failed"
        )
    
    # Cache the result
    if settings.CLOUD_CACHE_ENABLED:
        _expense_cache[cache_key] = (
            [item.model_dump() for item in result],
            utc_now().timestamp()
        )
    
    return result
