import json
import logging
import time
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cloud_accounts.models import CloudAccount
from app.config import settings
from app.recommendations.adapters.base import NormalizedRecommendation
from app.recommendations.adapters.factory import get_recommender_adapter
from app.recommendations.schemas import RecommendationType
from app.shared.crypto import decrypt
from app.shared.request_coalescing import coalesce_recommendations

logger = logging.getLogger(__name__)

# Cache TTL: Use configuration
_CACHE_TTL_SECONDS = settings.CACHE_TTL_RECOMMENDATIONS

# In-memory cache for CSP recommendations
_csp_cache: dict[str, tuple[list[dict], float]] = {}


def _get_cached_recommendations(
    cloud_account_id: str,
) -> list[dict] | None:
    """Check in-memory cache for recent CSP recommendations."""
    if not settings.CLOUD_CACHE_ENABLED:
        return None
    
    if cloud_account_id in _csp_cache:
        items, timestamp = _csp_cache[cloud_account_id]
        if time.time() - timestamp < _CACHE_TTL_SECONDS:
            logger.debug("CSP recommendations memory cache hit for account %s", cloud_account_id)
            return items
        # Expired, remove it
        del _csp_cache[cloud_account_id]
    
    return None


def _set_cached_recommendations(
    cloud_account_id: str,
    items: list[dict],
) -> None:
    """Store CSP recommendations in memory cache."""
    if settings.CLOUD_CACHE_ENABLED:
        _csp_cache[cloud_account_id] = (items, time.time())


async def _get_cached_recommendations_mongo(
    mongo_db: AsyncIOMotorDatabase,
    cloud_account_id: str,
) -> list[dict] | None:
    """Check MongoDB cache for recent CSP recommendations."""
    collection = mongo_db["csp_recommendations"]
    doc = await collection.find_one({"cloud_account_id": cloud_account_id})
    if doc and doc.get("fetched_at", 0) > time.time() - _CACHE_TTL_SECONDS:
        cached_items = doc.get("items", [])
        logger.debug("CSP recommendations MongoDB cache hit for account %s", cloud_account_id)
        
        # Also update memory cache
        _set_cached_recommendations(cloud_account_id, cached_items)
        
        return cached_items

    logger.debug("CSP recommendations cache miss for account %s", cloud_account_id)
    return None


async def _cache_recommendations(
    mongo_db: AsyncIOMotorDatabase,
    cloud_account_id: str,
    items: list[dict],
) -> None:
    """Store CSP recommendations in MongoDB cache."""
    collection = mongo_db["csp_recommendations"]
    await collection.update_one(
        {"cloud_account_id": cloud_account_id},
        {"$set": {
            "cloud_account_id": cloud_account_id,
            "items": items,
            "fetched_at": time.time(),
        }},
        upsert=True,
    )
    
    # Also update memory cache
    _set_cached_recommendations(cloud_account_id, items)


async def clear_recommendations_cache(
    mongo_db: AsyncIOMotorDatabase,
    cloud_account_id: Optional[str] = None,
) -> int:
    """Clear CSP recommendations cache from MongoDB and memory.
    
    Args:
        mongo_db: MongoDB database instance
        cloud_account_id: Optional specific account ID to clear. If None, clears all.
        
    Returns:
        Number of cache entries deleted
    """
    global _csp_cache
    
    # Clear MongoDB cache
    collection = mongo_db["csp_recommendations"]
    if cloud_account_id:
        result = await collection.delete_one({"cloud_account_id": cloud_account_id})
        
        # Also clear memory cache
        if cloud_account_id in _csp_cache:
            del _csp_cache[cloud_account_id]
        
        logger.info("Cleared recommendations cache for account %s", cloud_account_id)
        return result.deleted_count
    else:
        result = await collection.delete_many({})
        
        # Clear all memory cache
        count = len(_csp_cache)
        _csp_cache.clear()
        
        logger.info("Cleared all recommendations cache, deleted %d MongoDB entries, %d memory entries", 
                    result.deleted_count, count)
        return result.deleted_count + count


async def _fetch_recommendations_with_coalescing(
    account: CloudAccount,
    config: dict
) -> list[NormalizedRecommendation]:
    """Fetch recommendations with request coalescing.
    
    This prevents duplicate API calls when multiple concurrent users
    are requesting recommendations for the same cloud account.
    """
    adapter = get_recommender_adapter(account.type)
    if adapter is None:
        logger.warning("No recommendation adapter for cloud type %s", account.type)
        return []
    
    # Use coalescing for expensive recommendation API calls
    async def _fetch():
        return await adapter.fetch_recommendations(config)
    
    return await coalesce_recommendations(_fetch)


async def fetch_csp_recommendations(
    db: AsyncSession,
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
    cloud_account_ids: Optional[list[str]] = None,
) -> list[RecommendationType]:
    """Fetch CSP native recommendations for an organization's cloud accounts.

    Queries cloud accounts with process_recommendations=True, checks cache,
    and fetches from CSP APIs via adapters on cache miss. Uses request
    coalescing to handle concurrent users efficiently.
    
    Groups items by rec_type and returns list[RecommendationType] with source="csp_native".
    """
    logger.debug("Fetching CSP recommendations for org %s", org_id)
    
    # Query eligible cloud accounts
    query = select(CloudAccount).where(
        CloudAccount.organization_id == org_id,
        CloudAccount.process_recommendations.is_(True),
        CloudAccount.deleted_at.is_(None),
    )
    if cloud_account_ids:
        query = query.where(CloudAccount.id.in_(cloud_account_ids))

    result = await db.execute(query)
    accounts = list(result.scalars().all())

    if not accounts:
        logger.debug("No cloud accounts eligible for CSP recommendations in org %s", org_id)
        return []

    all_items: list[NormalizedRecommendation] = []

    for account in accounts:

        # Check memory cache first (fastest)
        cached = _get_cached_recommendations(account.id)
        if cached is not None:
            for item_dict in cached:
                all_items.append(NormalizedRecommendation(**item_dict))
            continue
        
        # Check MongoDB cache
        cached = await _get_cached_recommendations_mongo(mongo_db, account.id)
        if cached is not None:
            for item_dict in cached:
                all_items.append(NormalizedRecommendation(**item_dict))
            continue

        # Fetch from CSP with coalescing
        try:
            config = json.loads(decrypt(account.config))
        except (json.JSONDecodeError, TypeError, Exception) as e:
            logger.warning("Invalid config for cloud account %s: %s", account.id, str(e))
            continue

        items = await _fetch_recommendations_with_coalescing(account, config)
        logger.debug("Fetched %d CSP recommendations for account %s", len(items), account.id)

        # Tag items with cloud account info
        for item in items:
            item.cloud_type = account.type.value

        # Cache the results
        cache_data = [
            {
                "rec_type": i.rec_type,
                "name": i.name,
                "description": i.description,
                "category": i.category,
                "resource_id": i.resource_id,
                "resource_name": i.resource_name,
                "cloud_type": i.cloud_type,
                "region": i.region,
                "source_service": i.source_service,
                "saving": i.saving,
                "metadata": i.metadata,
            }
            for i in items
        ]
        await _cache_recommendations(mongo_db, account.id, cache_data)

        all_items.extend(items)


    # Group by rec_type into RecommendationType objects
    groups: dict[str, list[NormalizedRecommendation]] = {}
    for item in all_items:
        groups.setdefault(item.rec_type, []).append(item)

    # Import well-architected rules for enrichment
    from app.recommendations.service import _WELL_ARCHITECTED_RULES
    from app.recommendations.schemas import WellArchitectedRule

    results: list[RecommendationType] = []
    for rec_type, items in groups.items():
        first = items[0]
        total_saving = sum(i.saving for i in items)
        
        # Get well-architected rules for this recommendation type
        rule_dicts = _WELL_ARCHITECTED_RULES.get(rec_type, [])
        rules = [WellArchitectedRule(**r) for r in rule_dicts]
        
        results.append(RecommendationType(
            type=f"csp_{rec_type}",
            name=first.name,
            description=first.description,
            category=first.category,
            cloud_types=list({i.cloud_type for i in items}),
            count=len(items),
            saving=round(total_saving, 2),
            items=[
                {
                    "id": f"csp-{i.resource_id or idx}",
                    "resource_id": i.resource_id,
                    "resource_name": i.resource_name,
                    "cloud_type": i.cloud_type,
                    "region": i.region,
                    "saving": i.saving,
                    "source_service": i.source_service,
                    "dismissed": False,
                }
                for idx, i in enumerate(items)
            ],
            rules=rules,
            source="csp_native",
        ))
    logger.debug("Returning %d grouped CSP recommendation types", len(results))
    return results
