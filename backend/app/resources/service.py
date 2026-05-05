"""Resources service - Fetches real resource data from connected cloud accounts."""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import select

from app.cloud_accounts.adapters.aws import AWSAdapter
from app.cloud_accounts.adapters.azure import AzureAdapter
from app.cloud_accounts.adapters.gcp import GCPAdapter
from app.cloud_accounts.models import CloudAccount
from app.config import settings
from app.resources.schemas import PartialFailure, ResourceDetail, ResourceListResponse, ResourceResponse
from app.shared.crypto import decrypt
from app.shared.enums import CloudType
from app.shared.request_coalescing import coalesce_resource_discovery
from app.shared.sync_bounded_cache import SyncBoundedCache
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)

# Bounded LRU caches for resources (max 500 entries each)
_resource_cache = SyncBoundedCache(max_size=500, ttl_seconds=300, name="resources")
_resource_detail_cache = SyncBoundedCache(max_size=500, ttl_seconds=300, name="resource_details")


def get_cached_resources(org_id: str) -> list[ResourceResponse] | None:
    """Get cached resources if they exist and haven't expired.

    Public API for use by shared/degradation.py fallback chain.
    """
    if not settings.CLOUD_CACHE_ENABLED:
        return None
    return _resource_cache.get(org_id)


def _set_cached_resources(org_id: str, resources: list[ResourceResponse]) -> None:
    """Cache resources for the organization."""
    if settings.CLOUD_CACHE_ENABLED:
        _resource_cache.set(org_id, resources, ttl_seconds=settings.CACHE_TTL_RESOURCES)
        logger.debug("Cached %d resources for org %s", len(resources), org_id)


def _get_cached_resource_detail(resource_id: str) -> ResourceDetail | None:
    """Get cached resource detail if not expired."""
    if not settings.CLOUD_CACHE_ENABLED:
        return None
    return _resource_detail_cache.get(resource_id)


def _set_cached_resource_detail(resource_id: str, detail: ResourceDetail) -> None:
    """Cache resource detail."""
    if settings.CLOUD_CACHE_ENABLED:
        _resource_detail_cache.set(resource_id, detail, ttl_seconds=settings.CACHE_TTL_RESOURCES)


async def _get_cloud_accounts_with_adapters(org_id: str) -> tuple[list[tuple[CloudAccount, AWSAdapter | AzureAdapter | GCPAdapter]], list[PartialFailure]]:
    """Get cloud accounts and their adapters for the organization.

    Returns a tuple of (adapters, partial_failures).
    """
    from app.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            select(CloudAccount).where(
                CloudAccount.organization_id == org_id,
                CloudAccount.deleted_at.is_(None),
            )
        )
        accounts = list(result.scalars().all())

    adapters = []
    partial_failures: list[PartialFailure] = []
    for account in accounts:
        try:
            config = json.loads(decrypt(account.config))
            if account.type == CloudType.AWS:
                adapter = AWSAdapter(config)
                adapters.append((account, adapter))
            elif account.type == CloudType.AZURE:
                adapter = AzureAdapter(config)
                adapters.append((account, adapter))
            elif account.type == CloudType.GCP:
                adapter = GCPAdapter(config)
                adapters.append((account, adapter))
        except Exception as e:
            logger.error(f"Failed to create adapter for account {account.id}: {e}")
            partial_failures.append(PartialFailure(
                account_id=account.id,
                account_name=account.name,
                cloud_type=account.type.value,
                error=str(e)[:200],
            ))

    return adapters, partial_failures


async def _discover_resources_with_coalescing(
    account: CloudAccount,
    adapter: AWSAdapter | AzureAdapter | GCPAdapter
) -> list[dict]:
    """Discover resources with request coalescing.
    
    This prevents duplicate API calls when multiple concurrent users
    are requesting resources from the same cloud account.
    """
    cache_key = f"{account.id}:{account.organization_id}"
    
    async def _fetch():
        return await adapter.discover_resources()
    
    return await coalesce_resource_discovery(_fetch)


async def discover_all_resources(org_id: str) -> tuple[list[ResourceResponse], list[PartialFailure]]:
    """Discover resources from all connected cloud accounts.

    Returns a tuple of (resources, partial_failures).

    Public API for use by scheduler/executor.py.
    """
    adapters, adapter_failures = await _get_cloud_accounts_with_adapters(org_id)

    all_resources: list[ResourceResponse] = []
    now_ts = int(time.time())
    partial_failures: list[PartialFailure] = list(adapter_failures)

    for account, adapter in adapters:
        try:
            # Use coalesced resource discovery to prevent duplicate API calls
            if account.type in (CloudType.AZURE, CloudType.GCP):
                # For Azure/GCP, include per-resource costs so dashboard top resources
                # reflects the same values shown in cloud account details.
                resources = await adapter.discover_resources(include_costs=True)
            else:
                resources = await _discover_resources_with_coalescing(account, adapter)

            for idx, res in enumerate(resources):
                # Map state to active boolean
                state = res.get("state", "").lower()
                active = state in ("running", "available", "active", "in-use", "succeeded")

                # Parse launch_time or creation date for first_seen
                first_seen = now_ts - 30 * 86400  # Default to 30 days ago
                if res.get("launch_time"):
                    try:
                        dt = datetime.fromisoformat(res["launch_time"].replace("Z", "+00:00"))
                        first_seen = int(dt.timestamp())
                    except (ValueError, TypeError):
                        pass

                meta = res.get("meta", {})
                if meta.get("creation_date"):
                    try:
                        dt = datetime.fromisoformat(meta["creation_date"].replace("Z", "+00:00"))
                        first_seen = int(dt.timestamp())
                    except (ValueError, TypeError):
                        pass

                # Get costs from resource (Azure now includes daily_cost)
                daily_cost = res.get("daily_cost", 0) or 0
                total_cost_7d = res.get("total_cost_7d", 0) or 0

                all_resources.append(ResourceResponse(
                    id=f"{account.id}:{res['cloud_resource_id']}",
                    name=res.get("name", res["cloud_resource_id"]),
                    cloud_resource_id=res["cloud_resource_id"],
                    resource_type=res.get("resource_type", "Unknown"),
                    cloud_account_id=account.id,
                    cloud_account_name=account.name,
                    cloud_type=account.type.value,
                    region=res.get("region", "unknown"),
                    pool_id=None,
                    pool_name=None,
                    owner_id=None,
                    owner_name=None,
                    tags=res.get("tags", {}),
                    first_seen=first_seen,
                    last_seen=now_ts,
                    total_cost=total_cost_7d,
                    daily_cost=daily_cost,
                    active=active,
                ))
        except Exception as e:
            logger.error(f"Failed to discover resources for account {account.id}: {e}")
            partial_failures.append(PartialFailure(
                account_id=account.id,
                account_name=account.name,
                cloud_type=account.type.value,
                error=str(e)[:200],
            ))

    return all_resources, partial_failures


async def list_resources(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
    limit: int = 50,
    offset: int = 0,
    filters: dict | None = None,
) -> ResourceListResponse:
    """Return a paginated, optionally filtered list of resources.

    Uses caching and request coalescing to avoid repeated cloud API calls
    and handle concurrent users efficiently.
    """
    partial_failures: list[PartialFailure] = []

    # Try to get cached resources first
    all_resources = get_cached_resources(org_id)

    if all_resources is None:
        # Cache miss - fetch from cloud providers with coalescing
        all_resources, partial_failures = await discover_all_resources(org_id)
        # Cache the results
        _set_cached_resources(org_id, all_resources)

    filtered = all_resources

    if filters:
        if filters.get("cloud_type"):
            filtered = [r for r in filtered if r.cloud_type == filters["cloud_type"]]
        if filters.get("region"):
            filtered = [r for r in filtered if r.region == filters["region"]]
        if filters.get("resource_type"):
            filtered = [r for r in filtered if r.resource_type == filters["resource_type"]]
        if filters.get("cloud_account_id"):
            filtered = [r for r in filtered if r.cloud_account_id == filters["cloud_account_id"]]

    # Always rank by highest cost first for "Top Expensive Resources" consumers.
    filtered = sorted(
        filtered,
        key=lambda r: ((r.daily_cost or 0), (r.total_cost or 0)),
        reverse=True,
    )

    total_count = len(filtered)
    page = filtered[offset:offset + limit]

    has_errors = len(partial_failures) > 0
    if has_errors and len(partial_failures) > len(all_resources) / max(len(filtered), 1):
        logger.warning(
            f"Significant account failures during resource discovery: "
            f"{len(partial_failures)} accounts failed"
        )

    return ResourceListResponse(
        resources=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
        partial_failures=partial_failures,
        has_errors=has_errors,
    )


async def get_resource(
    mongo_db: AsyncIOMotorDatabase,
    resource_id: str,
) -> ResourceDetail | None:
    """Return detailed info for a single resource, or None if not found."""
    # Check cache first
    cached = _get_cached_resource_detail(resource_id)
    if cached:
        return cached
    
    # Parse the resource_id to get cloud_account_id and cloud_resource_id
    if ":" not in resource_id:
        return None
    
    parts = resource_id.split(":", 1)
    if len(parts) != 2:
        return None
    
    cloud_account_id, cloud_resource_id = parts
    
    # Get the cloud account
    from app.database import async_session_factory
    
    async with async_session_factory() as session:
        result = await session.execute(
            select(CloudAccount).where(
                CloudAccount.id == cloud_account_id,
                CloudAccount.deleted_at.is_(None),
            ).limit(1)
        )
        account = result.scalar_one_or_none()
    
    if not account:
        return None

    # Get all resources and find the matching one with coalescing
    adapters, failures = await _get_cloud_accounts_with_adapters(account.organization_id)

    for acc, adapter in adapters:
        if acc.id != cloud_account_id:
            continue
        
        try:
            # Use coalesced resource discovery
            resources = await _discover_resources_with_coalescing(acc, adapter)
            
            for res in resources:
                if res["cloud_resource_id"] == cloud_resource_id:
                    now_ts = int(time.time())
                    state = res.get("state", "").lower()
                    active = state in ("running", "available", "active", "in-use")
                    
                    first_seen = now_ts - 30 * 86400
                    meta = res.get("meta", {})
                    
                    # Build daily expenses (placeholder - would need Cost Explorer with resource tags)
                    today = utc_now().date()
                    daily_expenses = [
                        {"date": (today - timedelta(days=i)).isoformat(), "cost": 0}
                        for i in range(29, -1, -1)
                    ]
                    
                    # Build recommendations based on resource type
                    recommendations = []
                    if res.get("resource_type") in ("EC2 Instance", "Instance"):
                        if state == "running":
                            recommendations.append({
                                "type": "rightsizing_instances",
                                "name": "Rightsizing",
                                "saving": 0,
                                "description": f"Analyze CPU/memory utilization for {res.get('name', 'this instance')} to determine optimal instance size.",
                            })
                        elif state == "stopped":
                            recommendations.append({
                                "type": "obsolete_instances",
                                "name": "Remove Stopped Instance",
                                "saving": 0,
                                "description": "This instance is stopped. Consider terminating if no longer needed.",
                            })
                    
                    result = ResourceDetail(
                        id=resource_id,
                        name=res.get("name", cloud_resource_id),
                        cloud_resource_id=cloud_resource_id,
                        resource_type=res.get("resource_type", "Unknown"),
                        cloud_account_id=account.id,
                        cloud_account_name=account.name,
                        cloud_type=account.type.value,
                        region=res.get("region", "unknown"),
                        pool_id=None,
                        pool_name=None,
                        owner_id=None,
                        owner_name=None,
                        tags=res.get("tags", {}),
                        first_seen=first_seen,
                        last_seen=now_ts,
                        total_cost=0,
                        daily_cost=0,
                        active=active,
                        meta=meta,
                        recommendations=recommendations,
                        daily_expenses=daily_expenses,
                    )
                    
                    # Cache the result
                    _set_cached_resource_detail(resource_id, result)
                    
                    return result
        except Exception as e:
            logger.warning(f"Failed to get resource details from account {acc.name}: {e}")
            continue
    
    return None


async def invalidate_resource_cache(org_id: str | None = None) -> None:
    """Invalidate resource cache for an organization or globally.
    
    Args:
        org_id: Organization ID to invalidate, or None for all
    """
    global _resource_cache, _resource_detail_cache
    
    if org_id:
        # Remove org-level resource cache
        if org_id in _resource_cache:
            del _resource_cache[org_id]
            logger.info(f"Invalidated resource cache for org {org_id}")
        
        # Remove resource detail cache entries for this org
        keys_to_remove = [
            k for k in _resource_detail_cache.keys()
            if k.startswith(f"{org_id}:") or any(
                k.startswith(f"{acc_id}:")
                for acc_id in _get_account_ids_for_org(org_id)
            )
        ]
        for key in keys_to_remove:
            del _resource_detail_cache[key]
    else:
        # Clear all caches
        count = len(_resource_cache)
        _resource_cache.clear()
        _resource_detail_cache.clear()
        logger.info(f"Invalidated all resource caches ({count} org entries)")


def _get_account_ids_for_org(org_id: str) -> list[str]:
    """Get cloud account IDs for an organization (async, simplified)."""
    # This is a placeholder - in production you'd query the database
    return []


async def refresh_resources(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
) -> ResourceListResponse:
    """Force refresh of resources from cloud providers.

    This bypasses the cache and fetches fresh data from all cloud accounts.
    """
    # Invalidate cache first
    await invalidate_resource_cache(org_id)

    # Fetch fresh data
    all_resources, partial_failures = await discover_all_resources(org_id)
    _set_cached_resources(org_id, all_resources)

    has_errors = len(partial_failures) > 0
    if has_errors and len(partial_failures) > len(all_resources) / max(len(all_resources[:50]), 1):
        logger.warning(
            f"Significant account failures during resource refresh: "
            f"{len(partial_failures)} accounts failed"
        )

    return ResourceListResponse(
        resources=all_resources[:50],
        total_count=len(all_resources),
        limit=50,
        offset=0,
        partial_failures=partial_failures,
        has_errors=has_errors,
    )
