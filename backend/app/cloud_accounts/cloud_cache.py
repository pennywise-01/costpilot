"""Cloud data caching module using Redis for expensive API calls.

This module provides caching for cloud provider API responses to reduce
latency and prevent rate limiting issues when multiple concurrent users
are accessing the system.
"""

import hashlib
import json
import logging
from datetime import timedelta
from typing import Any, Callable, ParamSpec, TypeVar
from functools import wraps

from app.config import settings
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)

# Type variables for generic function signatures
P = ParamSpec("P")
T = TypeVar("T")


class CloudCache:
    """Redis-backed cache for cloud API responses.
    
    Provides automatic serialization, TTL management, and cache key generation
    for expensive cloud provider API calls.
    """

    def __init__(self, redis_client: Any = None):
        """Initialize cloud cache.
        
        Args:
            redis_client: Optional Redis client for distributed caching.
                         Falls back to in-memory cache if not provided.
        """
        self._redis = redis_client
        self._memory_cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = getattr(settings, 'CLOUD_CACHE_TTL_SECONDS', 300)  # 5 minutes

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a consistent cache key from arguments."""
        key_data = f"{prefix}:{json.dumps(args, sort_keys=True, default=str)}:{json.dumps(kwargs, sort_keys=True, default=str)}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    async def get(self, key: str) -> Any | None:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        # Try Redis first
        if self._redis:
            try:
                value = await self._redis.get(f"cloud:{key}")
                if value:
                    logger.debug(f"Cache hit (Redis): {key[:16]}...")
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")
        
        # Fallback to memory cache
        if key in self._memory_cache:
            value, expires_at = self._memory_cache[key]
            if expires_at > utc_now():
                logger.debug(f"Cache hit (memory): {key[:16]}...")
                return value
            # Expired, clean up
            del self._memory_cache[key]

        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl_seconds: TTL in seconds, uses default if not specified
        """
        ttl = ttl_seconds or self._default_ttl
        expires_at = utc_now() + timedelta(seconds=ttl)
        
        # Store in memory cache
        self._memory_cache[key] = (value, expires_at)
        
        # Also store in Redis if available
        if self._redis:
            try:
                await self._redis.setex(
                    f"cloud:{key}",
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")
        
        logger.debug(f"Cached value: {key[:16]}... (TTL: {ttl}s)")

    async def delete(self, key: str) -> None:
        """Delete value from cache.
        
        Args:
            key: Cache key to delete
        """
        # Remove from memory cache
        self._memory_cache.pop(key, None)
        
        # Remove from Redis
        if self._redis:
            try:
                await self._redis.delete(f"cloud:{key}")
            except Exception as e:
                logger.warning(f"Redis cache delete error: {e}")

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (simple string match, not regex)
            
        Returns:
            Number of entries cleared
        """
        cleared = 0
        
        # Clear memory cache
        keys_to_delete = [k for k in self._memory_cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self._memory_cache[key]
            cleared += 1
        
        # Clear Redis cache
        if self._redis:
            try:
                # Scan for keys matching pattern
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor,
                        match=f"cloud:*{pattern}*",
                        count=100
                    )
                    if keys:
                        await self._redis.delete(*keys)
                        cleared += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Redis cache clear error: {e}")
        
        logger.info(f"Cleared {cleared} cache entries matching '{pattern}'")
        return cleared

    def cached(
        self,
        prefix: str,
        ttl_seconds: int | None = None,
        key_builder: Callable[..., str] | None = None
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator to cache function results.
        
        Args:
            prefix: Cache key prefix
            ttl_seconds: TTL for cached results
            key_builder: Optional custom key builder function
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                # Build cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = self._generate_key(prefix, *args, **kwargs)
                
                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Call the function
                result = await func(*args, **kwargs)
                
                # Cache the result
                await self.set(cache_key, result, ttl_seconds)
                
                return result
            
            # Attach cache management methods
            wrapper.cache_delete = lambda **kwargs: self.delete(
                key_builder(**kwargs) if key_builder else self._generate_key(prefix, **kwargs)
            )
            wrapper.cache_clear = lambda pattern: self.clear_pattern(pattern)
            
            return wrapper
        return decorator


# Global cache instance
_cloud_cache: CloudCache | None = None


def get_cloud_cache(redis_client: Any = None) -> CloudCache:
    """Get or create global cloud cache instance.
    
    Args:
        redis_client: Optional Redis client to use
        
    Returns:
        CloudCache instance
    """
    global _cloud_cache
    if _cloud_cache is None:
        _cloud_cache = CloudCache(redis_client)
    return _cloud_cache


def invalidate_cloud_cache(org_id: str | None = None) -> None:
    """Invalidate cloud cache for an organization.
    
    This should be called when cloud account credentials change
    or when manual refresh is requested.
    
    Args:
        org_id: Organization ID to invalidate, or None for all
    """
    cache = get_cloud_cache()
    if org_id:
        # Run async clear in sync context
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cache.clear_pattern(org_id))
            else:
                loop.run_until_complete(cache.clear_pattern(org_id))
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for org {org_id}: {e}")
    else:
        # Clear all cloud cache
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cache.clear_pattern(""))
            else:
                loop.run_until_complete(cache.clear_pattern(""))
        except Exception as e:
            logger.warning(f"Failed to invalidate all cache: {e}")


# Convenience decorator for caching cloud API calls
def cloud_cached(
    prefix: str,
    ttl_seconds: int | None = None,
    key_builder: Callable[..., str] | None = None
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to cache cloud API call results.
    
    Usage:
        @cloud_cached("aws_costs", ttl_seconds=300)
        async def get_aws_costs(org_id: str, start_date: str, end_date: str):
            # Expensive API call
            return await aws_client.get_costs(start_date, end_date)
    
    Args:
        prefix: Cache key prefix for this type of data
        ttl_seconds: Cache TTL in seconds (default: 5 minutes)
        key_builder: Optional custom key builder function
        
    Returns:
        Decorated function with caching
    """
    cache = get_cloud_cache()
    return cache.cached(prefix, ttl_seconds, key_builder)
