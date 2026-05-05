"""Graceful degradation strategies for fault tolerance.

ARCHITECTURE NOTE: This module uses deferred (in-function) imports to reach
into domain service modules (expenses, resources, cost_cache, recommendations).
This is an intentional upward import from the shared package into domain
modules. The deferred imports prevent circular dependencies at module load
time, but they create a hidden dependency graph that static analysis tools
cannot detect.

The fallback chain pattern is: try live → try cache → return degraded.
Each layer has its own try/except. Callers MUST inspect the returned
``data_source`` ("live", "cached", "stale", "unavailable") and
``freshness_seconds`` tuple values to understand what happened.
"""

from typing import TypeVar, Callable, Optional, Any, Protocol
from functools import wraps
from datetime import datetime, timedelta
import logging

from fastapi import Response
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)
T = TypeVar('T')


class CacheClient(Protocol):
    """Protocol for cache clients."""
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int = 300) -> None: ...


class DegradationStrategy:
    """Strategy for graceful degradation when services fail."""

    async def fallback(self, *args, **kwargs) -> Any:
        """Return fallback value when primary fails."""
        raise NotImplementedError

    async def should_attempt_primary(self) -> bool:
        """Check if we should attempt primary operation."""
        return True


class CacheFallbackStrategy(DegradationStrategy):
    """Fallback to cached data."""

    def __init__(
        self,
        cache_client: CacheClient,
        cache_key: str,
        max_staleness: timedelta = timedelta(hours=24)
    ):
        self.cache = cache_client
        self.cache_key = cache_key
        self.max_staleness = max_staleness

    async def fallback(self, *args, **kwargs) -> Any:
        cached = await self.cache.get(self.cache_key)
        if cached:
            logger.info(f"Returning cached data for {self.cache_key}")
            # Add metadata to indicate degraded response
            if isinstance(cached, dict):
                return {
                    **cached,
                    "_degraded": True,
                    "_cached_at": utc_now().isoformat(),
                    "_stale": True
                }
            return cached
        return None


class StaticFallbackStrategy(DegradationStrategy):
    """Fallback to static/default value."""

    def __init__(self, fallback_value: Any):
        self.fallback_value = fallback_value

    async def fallback(self, *args, **kwargs) -> Any:
        return self.fallback_value


class EmptyFallbackStrategy(DegradationStrategy):
    """Fallback to empty result."""

    async def fallback(self, *args, **kwargs) -> Any:
        return []


class EmptyDictFallbackStrategy(DegradationStrategy):
    """Fallback to empty dictionary."""

    async def fallback(self, *args, **kwargs) -> Any:
        return {}


class DegradedResponse:
    """Wrapper for degraded responses."""

    def __init__(
        self,
        data: Any,
        is_degraded: bool = False,
        reason: Optional[str] = None,
        fallback_type: Optional[str] = None
    ):
        self.data = data
        self.is_degraded = is_degraded
        self.reason = reason
        self.fallback_type = fallback_type
        self.timestamp = utc_now()

    def to_dict(self) -> dict:
        result = {
            "data": self.data,
            "_meta": {
                "is_degraded": self.is_degraded,
                "timestamp": self.timestamp.isoformat()
            }
        }
        if self.reason:
            result["_meta"]["reason"] = self.reason
        if self.fallback_type:
            result["_meta"]["fallback_type"] = self.fallback_type
        return result

    def unwrap(self) -> Any:
        """Get just the data without metadata."""
        return self.data


def with_fallback(strategy: DegradationStrategy):
    """Decorator for graceful degradation."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> DegradedResponse:
            # Try primary operation
            if await strategy.should_attempt_primary():
                try:
                    result = await func(*args, **kwargs)
                    return DegradedResponse(result, is_degraded=False)
                except Exception as e:
                    logger.warning(f"Primary operation failed: {e}. Attempting fallback.")
                    primary_error = str(e)
            else:
                primary_error = "Primary operation skipped"

            # Try fallback
            try:
                fallback_result = await strategy.fallback(*args, **kwargs)
                if fallback_result is not None:
                    return DegradedResponse(
                        fallback_result,
                        is_degraded=True,
                        reason=primary_error,
                        fallback_type=type(strategy).__name__
                    )
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")

            # Both failed - re-raise original error
            raise

        return wrapper
    return decorator


class ServiceDegradationManager:
    """Manager for service degradation states."""

    def __init__(self):
        self._degraded_services: dict[str, datetime] = {}
        self._auto_recovery_timeout = timedelta(minutes=5)

    def mark_degraded(self, service_name: str) -> None:
        """Mark a service as degraded."""
        self._degraded_services[service_name] = utc_now()
        logger.warning(f"Service {service_name} marked as degraded")

    def mark_recovered(self, service_name: str) -> None:
        """Mark a service as recovered."""
        if service_name in self._degraded_services:
            del self._degraded_services[service_name]
            logger.info(f"Service {service_name} marked as recovered")

    def is_degraded(self, service_name: str) -> bool:
        """Check if a service is currently degraded."""
        if service_name not in self._degraded_services:
            return False

        # Check if auto-recovery timeout has passed
        degraded_since = self._degraded_services[service_name]
        if utc_now() - degraded_since > self._auto_recovery_timeout:
            self.mark_recovered(service_name)
            return False

        return True

    def get_degraded_services(self) -> list[str]:
        """Get list of currently degraded services."""
        # Clean up expired entries
        now = utc_now()
        expired = [
            name for name, since in self._degraded_services.items()
            if now - since > self._auto_recovery_timeout
        ]
        for name in expired:
            self.mark_recovered(name)

        return list(self._degraded_services.keys())


# Global degradation manager
degradation_manager = ServiceDegradationManager()


# Common fallback strategies

def _compute_freshness_seconds(cached_at: Any) -> int:
    """Compute freshness in seconds from a cached_at timestamp."""
    if cached_at is None:
        return -1
    try:
        if isinstance(cached_at, str):
            from datetime import datetime, timezone
            cached_at = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        if hasattr(cached_at, "timestamp"):
            # Ensure timezone-aware for subtraction with utc_now()
            if cached_at.tzinfo is None:
                from datetime import timezone
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            return int((utc_now() - cached_at).total_seconds())
    except Exception:
        pass
    return -1


async def get_expenses_with_fallback(
    db,
    org_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    group_by: str = "cloud",
    allow_stale: bool = True,
) -> tuple[Any, str, int]:
    """Try live expenses, fall back to cache, then to empty.

    Returns (data, data_source, freshness_seconds).
    """
    # Try live first
    try:
        from app.expenses.service import get_expense_breakdown, get_expense_summary
        from app.database import get_mongo_db

        mongo_db = get_mongo_db()
        if start_date and end_date:
            result = await get_expense_breakdown(mongo_db, org_id, start_date, end_date, group_by)
        else:
            result = await get_expense_summary(mongo_db, org_id)
        return result, "live", 0
    except Exception as e:
        logger.warning(f"Live expense fetch failed for org {org_id}: {e}")

    # Try cache
    try:
        from app.cost_cache.service import get_cached_summary, get_cached_breakdown

        if start_date and end_date:
            cached = await get_cached_breakdown(db, org_id, start_date, end_date, group_by, allow_stale=allow_stale)
        else:
            cached = await get_cached_summary(db, org_id, allow_stale=allow_stale)

        if cached is not None:
            freshness = _compute_freshness_seconds(getattr(cached, "cached_at", None))
            data_source = "stale" if freshness > 0 and getattr(cached, "data_source", None) == "cache" else "cached"
            return cached, data_source, freshness
    except Exception as e:
        logger.warning(f"Cache fallback failed for org {org_id}: {e}")

    # Return degraded response
    from app.expenses.schemas import ExpenseBreakdown

    degraded = ExpenseBreakdown(
        total=0,
        previous_total=0,
        start_date=start_date or "",
        end_date=end_date or "",
        breakdown=[],
        daily_totals=[],
        partial_failures=[],
        has_errors=True,
    )
    return degraded, "unavailable", -1


async def get_resources_with_fallback(
    db,
    org_id: str,
    limit: int = 50,
    offset: int = 0,
    filters: dict | None = None,
) -> tuple[Any, str, int]:
    """Try live resources, fall back to cache, then to empty.

    Returns (data, data_source, freshness_seconds).
    """
    # Try live first
    try:
        from app.resources.service import list_resources
        from app.database import get_mongo_db

        mongo_db = get_mongo_db()
        result = await list_resources(mongo_db, org_id, limit, offset, filters)
        return result, "live", 0
    except Exception as e:
        logger.warning(f"Live resource fetch failed for org {org_id}: {e}")

    # Try cache - resources service has internal cache
    try:
        from app.resources.service import get_cached_resources

        cached = get_cached_resources(org_id)
        if cached is not None:
            from app.resources.schemas import ResourceListResponse

            result = ResourceListResponse(
                resources=cached,
                total_count=len(cached),
                limit=limit,
                offset=offset,
                partial_failures=[],
                has_errors=False,
            )
            return result, "cached", -1
    except Exception as e:
        logger.warning(f"Cache fallback failed for org {org_id}: {e}")

    # Return degraded response
    from app.resources.schemas import ResourceListResponse

    degraded = ResourceListResponse(
        resources=[],
        total_count=0,
        limit=limit,
        offset=offset,
        partial_failures=[],
        has_errors=True,
    )
    return degraded, "unavailable", -1


async def get_recommendations_with_fallback(
    db,
    org_id: str,
    cloud_account_id: list[str] | None = None,
) -> tuple[Any, str, int]:
    """Try live recommendations, fall back to cache, then to empty.

    Returns (data, data_source, freshness_seconds).
    """
    # Try live first
    try:
        from app.recommendations.service import get_recommendations_overview
        from app.database import get_mongo_db

        mongo_db = get_mongo_db()
        result = await get_recommendations_overview(mongo_db, org_id, cloud_account_id, db=db)
        return result, "live", 0
    except Exception as e:
        logger.warning(f"Live recommendations fetch failed for org {org_id}: {e}")

    # Try cache - recommendations don't have a simple org-level cache,
    # so we skip directly to degraded response
    logger.debug(f"No cache fallback available for recommendations org {org_id}")

    # Return degraded response
    from app.recommendations.schemas import RecommendationsOverview

    degraded = RecommendationsOverview(
        total_saving=0,
        total_count=0,
        last_run=None,
        next_run=None,
        categories={},
        recommendations=[],
    )
    return degraded, "unavailable", -1


def apply_degradation_headers(response: Response, data_source: str, freshness_seconds: int) -> None:
    """Apply X-Data-Source and X-Data-Freshness headers to a FastAPI response."""
    response.headers["X-Data-Source"] = data_source
    response.headers["X-Data-Freshness"] = str(freshness_seconds)
