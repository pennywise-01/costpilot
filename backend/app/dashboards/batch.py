"""Batch widget data endpoint — groups widgets by data source, fetches once, maps back."""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dashboards.schemas import WidgetDataRequest
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)

# --- Data source grouping ---

STAT_CARD_SUMMARY_METRICS = {
    "monthly_spend", "last_month_spend", "forecast", "change_percent",
}
STAT_CARD_RECOMMENDATION_METRICS = {"potential_savings", "recommendation_count"}
STAT_CARD_CLOUD_ACCOUNT_METRICS = {"cloud_account_count"}
STAT_CARD_RESOURCE_METRICS = {"resource_count"}

BREAKDOWN_METRICS = {
    "cost_trend", "cost_by_cloud", "cost_by_service", "cost_by_region",
    "cloud_distribution", "service_distribution", "cost_trend_by_cloud",
    "cost_by_tag",
}

BUDGET_METRICS = {"budget_vs_spend"}
TREND_COMPARISON_METRICS = {"cost_comparison_by_cloud", "cost_comparison_by_service"}

RESOURCE_METRICS = {"top_resources"}
RECOMMENDATION_METRICS = {"recommendations", "recommendation_categories"}
POOL_METRICS = {"pool_status"}
CLOUD_ACCOUNT_HEALTH_METRICS = {"cloud_accounts", "cloud_account_health"}


def _group_by_data_source(widgets: list[WidgetDataRequest]) -> dict[str, list[WidgetDataRequest]]:
    """Group widget requests by their underlying data source for dedup."""
    groups: dict[str, list[WidgetDataRequest]] = defaultdict(list)
    for w in widgets:
        metric = w.metric
        if metric in STAT_CARD_SUMMARY_METRICS:
            groups["expense_summary"].append(w)
        elif metric in BREAKDOWN_METRICS:
            # Different group_by params need different breakdown calls
            group_by = w.params.get("groupBy", w.params.get("group_by", "cloud"))
            groups[f"expense_breakdown:{group_by}"].append(w)
        elif metric in STAT_CARD_RECOMMENDATION_METRICS:
            groups["recommendations_overview"].append(w)
        elif metric in STAT_CARD_CLOUD_ACCOUNT_METRICS or metric in CLOUD_ACCOUNT_HEALTH_METRICS:
            groups["cloud_accounts"].append(w)
        elif metric in STAT_CARD_RESOURCE_METRICS or metric in RESOURCE_METRICS:
            groups["resources"].append(w)
        elif metric in RECOMMENDATION_METRICS:
            groups["recommendations_overview"].append(w)
        elif metric in POOL_METRICS:
            groups["pools"].append(w)
        elif metric in BUDGET_METRICS:
            groups["budget"].append(w)
        elif metric in TREND_COMPARISON_METRICS:
            group_by = w.params.get("groupBy", w.params.get("group_by", "cloud"))
            groups[f"expense_breakdown:{group_by}"].append(w)
        else:
            groups[f"unknown:{metric}"].append(w)
    return groups


# --- Data fetchers per source ---


async def _fetch_expense_summary(db: AsyncSession, org_id: str) -> dict:
    from app.cost_cache.service import get_cached_summary
    summary = await get_cached_summary(db, org_id, allow_stale=True)
    return summary.model_dump()


async def _fetch_expense_breakdown(db: AsyncSession, org_id: str, group_by: str = "cloud", days: int = 30) -> dict:
    from app.cost_cache.service import get_cached_breakdown
    end_date = utc_now().date().isoformat()
    start_date = (utc_now().date() - timedelta(days=days)).isoformat()
    breakdown = await get_cached_breakdown(db, org_id, start_date, end_date, group_by=group_by, allow_stale=True)
    return breakdown.model_dump()


async def _fetch_resources(db: AsyncSession, org_id: str, limit: int = 50) -> dict:
    from app.database import get_mongo_db
    from app.resources.service import list_resources
    mongo_db = get_mongo_db()
    result = await list_resources(mongo_db, org_id, limit=limit)
    return result.model_dump()


async def _fetch_recommendations_overview(db: AsyncSession, org_id: str) -> dict:
    from app.database import get_mongo_db
    from app.recommendations.service import get_recommendations_overview
    mongo_db = get_mongo_db()
    result = await get_recommendations_overview(mongo_db, org_id, db=db)
    return result.model_dump()


async def _fetch_cloud_accounts(db: AsyncSession, org_id: str) -> dict:
    from app.cloud_accounts.service import list_cloud_accounts
    accounts, count = await list_cloud_accounts(db, org_id, limit=500)
    return {
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type.value,
                "organization_id": a.organization_id,
            }
            for a in accounts
        ],
        "count": count,
    }


async def _fetch_pools(db: AsyncSession, org_id: str) -> dict:
    from app.pools.service import get_pool_tree
    pools = await get_pool_tree(db, org_id)
    return {
        "pools": [
            {
                "id": p.id,
                "name": p.name,
                "limit": p.limit,
                "purpose": p.purpose.value if p.purpose else None,
            }
            for p in pools
        ],
        "count": len(pools),
    }


async def _fetch_budget(db: AsyncSession, org_id: str) -> dict:
    from app.cost_cache.service import get_cached_summary
    from app.organizations.service import get_organization
    from app.pools.service import get_pool_tree

    # Get budget from org's root pool via service layer
    try:
        org = await get_organization(db, org_id)
        budget = 0.0
        if org.pool_id:
            pools = await get_pool_tree(db, org_id)
            for p in pools:
                if p.id == org.pool_id:
                    budget = float(p.limit)
                    break
    except Exception:
        budget = 0.0

    # Get current spend from cache
    summary = await get_cached_summary(db, org_id, allow_stale=True)
    return {
        "budget": budget,
        "spent": summary.this_month_total,
        "forecast": summary.this_month_forecast,
        "data_source": summary.data_source,
    }


# --- Metric → response mapping ---

def _map_summary_to_metric(metric: str, summary_data: dict) -> dict:
    mapping = {
        "monthly_spend": {"value": summary_data.get("this_month_total", 0)},
        "last_month_spend": {"value": summary_data.get("last_month_total", 0)},
        "forecast": {"value": summary_data.get("this_month_forecast", 0)},
        "change_percent": {"value": summary_data.get("change_percent", 0)},
    }
    result = mapping.get(metric, {"value": 0})
    result["data_source"] = summary_data.get("data_source", "cache")
    return result


def _map_breakdown_to_metric(metric: str, breakdown_data: dict) -> dict:
    if metric == "cost_trend":
        return {
            "daily_totals": breakdown_data.get("daily_totals", []),
            "data_source": breakdown_data.get("data_source", "cache"),
        }
    elif metric == "cost_trend_by_cloud":
        return {
            "breakdown": breakdown_data.get("breakdown", []),
            "data_source": breakdown_data.get("data_source", "cache"),
        }
    elif metric in ("cost_by_cloud", "cost_by_service", "cost_by_region", "cost_by_tag"):
        return {
            "breakdown": breakdown_data.get("breakdown", []),
            "data_source": breakdown_data.get("data_source", "cache"),
        }
    elif metric in ("cloud_distribution", "service_distribution"):
        return {
            "breakdown": breakdown_data.get("breakdown", []),
            "data_source": breakdown_data.get("data_source", "cache"),
        }
    elif metric in ("cost_comparison_by_cloud", "cost_comparison_by_service"):
        return {
            "breakdown": breakdown_data.get("breakdown", []),
            "data_source": breakdown_data.get("data_source", "cache"),
        }
    return {"data_source": "unknown"}


def _map_recommendations_to_metric(metric: str, rec_data: dict) -> dict:
    if metric in ("potential_savings", "recommendation_count"):
        return {
            "value": rec_data.get("total_saving" if metric == "potential_savings" else "total_count", 0),
            "data_source": "cache",
        }
    elif metric == "recommendations":
        return {
            "recommendations": rec_data.get("recommendations", []),
            "total_saving": rec_data.get("total_saving", 0),
            "total_count": rec_data.get("total_count", 0),
            "categories": rec_data.get("categories", {}),
        }
    elif metric == "recommendation_categories":
        return {
            "categories": rec_data.get("categories", {}),
            "recommendations": rec_data.get("recommendations", []),
            "total_saving": rec_data.get("total_saving", 0),
        }
    return {"data_source": "unknown"}


def _map_resources_to_metric(metric: str, res_data: dict) -> dict:
    if metric == "top_resources":
        return {"resources": res_data.get("resources", [])[:10]}
    elif metric == "resource_count":
        return {"value": res_data.get("total_count", 0)}
    return {"data_source": "unknown"}


def _map_cloud_accounts_to_metric(metric: str, ca_data: dict) -> dict:
    if metric == "cloud_account_count":
        return {"value": ca_data.get("count", 0)}
    elif metric == "cloud_accounts":
        return {"accounts": ca_data.get("accounts", [])}
    elif metric == "cloud_account_health":
        return {"accounts": ca_data.get("accounts", [])}
    return {"data_source": "unknown"}


def _map_pools_to_metric(metric: str, pool_data: dict) -> dict:
    if metric == "pool_status":
        return {"pools": pool_data.get("pools", []), "count": pool_data.get("count", 0)}
    return {"data_source": "unknown"}


def _map_budget_to_metric(metric: str, budget_data: dict) -> dict:
    if metric == "budget_vs_spend":
        return {
            "budget": budget_data.get("budget", 0),
            "spent": budget_data.get("spent", 0),
            "forecast": budget_data.get("forecast", 0),
            "data_source": budget_data.get("data_source", "cache"),
        }
    return {"data_source": "unknown"}


# --- Main batch handler ---

async def fetch_batch_widget_data(
    db: AsyncSession,
    org_id: str,
    widgets: list[WidgetDataRequest],
) -> dict:
    """Fetch all widget data in a single batch, grouped by data source."""
    groups = _group_by_data_source(widgets)

    # Fetch each data source once in parallel
    fetch_tasks = {}
    for source_key, widget_list in groups.items():
        if source_key.startswith("expense_breakdown:"):
            group_by = source_key.split(":")[1]
            days = widget_list[0].params.get("days", 30) if widget_list else 30
            fetch_tasks[source_key] = _fetch_expense_breakdown(db, org_id, group_by=group_by, days=days)
        elif source_key == "expense_summary":
            fetch_tasks[source_key] = _fetch_expense_summary(db, org_id)
        elif source_key == "resources":
            limit = max(w.params.get("limit", 50) for w in widget_list) if widget_list else 50
            fetch_tasks[source_key] = _fetch_resources(db, org_id, limit=limit)
        elif source_key == "recommendations_overview":
            fetch_tasks[source_key] = _fetch_recommendations_overview(db, org_id)
        elif source_key == "cloud_accounts":
            fetch_tasks[source_key] = _fetch_cloud_accounts(db, org_id)
        elif source_key == "pools":
            fetch_tasks[source_key] = _fetch_pools(db, org_id)
        elif source_key == "budget":
            fetch_tasks[source_key] = _fetch_budget(db, org_id)

    # Execute in parallel with return_exceptions=True for partial failure tolerance
    source_keys = list(fetch_tasks.keys())
    source_coros = [fetch_tasks[k] for k in source_keys]
    source_results = await asyncio.gather(*source_coros, return_exceptions=True)

    # Build data map: source_key → result
    source_data: dict[str, dict] = {}
    source_errors: dict[str, str] = {}
    for key, result in zip(source_keys, source_results):
        if isinstance(result, Exception):
            source_errors[key] = str(result)[:200]
            logger.error("Batch data source %s failed: %s", key, result)
        else:
            source_data[key] = result

    # Map results back to individual widget metrics
    data: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for source_key, widget_list in groups.items():
        if source_key in source_errors:
            for w in widget_list:
                errors[w.metric] = source_errors[source_key]
            continue

        raw = source_data.get(source_key, {})

        for w in widget_list:
            metric = w.metric
            try:
                if source_key == "expense_summary" or source_key.startswith("expense_summary"):
                    data[metric] = _map_summary_to_metric(metric, raw)
                elif source_key.startswith("expense_breakdown"):
                    data[metric] = _map_breakdown_to_metric(metric, raw)
                elif source_key == "recommendations_overview":
                    data[metric] = _map_recommendations_to_metric(metric, raw)
                elif source_key == "resources":
                    data[metric] = _map_resources_to_metric(metric, raw)
                elif source_key == "cloud_accounts":
                    data[metric] = _map_cloud_accounts_to_metric(metric, raw)
                elif source_key == "pools":
                    data[metric] = _map_pools_to_metric(metric, raw)
                elif source_key == "budget":
                    data[metric] = _map_budget_to_metric(metric, raw)
                else:
                    errors[metric] = f"Unknown data source: {source_key}"
            except Exception as e:
                errors[metric] = str(e)[:200]

    # Determine overall meta
    all_sources = set()
    for v in data.values():
        ds = v.get("data_source")
        if ds:
            all_sources.add(ds)

    meta = {
        "data_source": ",".join(sorted(all_sources)) if all_sources else "unknown",
        "freshness": "fresh" if "live" not in all_sources else "mixed",
        "generated_at": utc_now().isoformat(),
    }

    return {
        "data": data,
        "errors": errors,
        "meta": meta,
    }
