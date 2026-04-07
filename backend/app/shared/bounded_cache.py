"""Bounded LRU cache with TTL support."""

import asyncio
import time
from collections import OrderedDict
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class BoundedCache:
    """LRU cache with TTL and max size enforcement.
    
    Thread-safe with asyncio.Lock. Automatically evicts:
    - Expired entries on access
    - Oldest entries when at capacity
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300, name: str = "default"):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.name = name
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if expired or not found."""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            value, expires_at = self._cache[key]
            if expires_at < time.time():
                # Expired - remove
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value with TTL. Evicts oldest if at capacity."""
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        expires_at = time.time() + ttl
        
        async with self._lock:
            if key in self._cache:
                # Update existing - move to end
                self._cache.move_to_end(key)
            
            self._cache[key] = (value, expires_at)
            
            # Evict oldest if over capacity
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache '{self.name}' evicted oldest entry: {oldest_key}")

    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if found."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """Clear all entries. Returns count of cleared entries."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def cleanup(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        async with self._lock:
            now = time.time()
            expired_keys = [k for k, (_, exp) in self._cache.items() if exp < now]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    async def stats(self) -> dict:
        """Get cache statistics."""
        async with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "name": self.name,
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
                "utilization_percent": round(len(self._cache) / self.max_size * 100, 2) if self.max_size > 0 else 0,
            }

    async def keys(self) -> list[str]:
        """List all keys (for debugging)."""
        async with self._lock:
            return list(self._cache.keys())


def create_bounded_cache(max_size: int = 1000, ttl_seconds: int = 300, name: str = "default") -> BoundedCache:
    """Factory function to create a BoundedCache instance."""
    return BoundedCache(max_size=max_size, ttl_seconds=ttl_seconds, name=name)
