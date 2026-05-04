"""Synchronous bounded LRU cache with TTL support.

Unlike the async BoundedCache in bounded_cache.py, this variant uses
plain threading locks and synchronous access, making it safe to use
from both sync and async contexts without awaiting.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class SyncBoundedCache:
    """Synchronous LRU cache with TTL and max size enforcement.

    Thread-safe with threading.Lock. Automatically evicts:
    - Expired entries on access
    - Oldest entries when at capacity

    Use this for in-memory caches that don't need async I/O.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300, name: str = "default"):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.name = name
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if expired or not found."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            value, expires_at = self._cache[key]
            if expires_at < time.time():
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value with TTL. Evicts oldest if at capacity."""
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        expires_at = time.time() + ttl

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)

            self._cache[key] = (value, expires_at)

            # Evict oldest if over capacity
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug("Cache '%s' evicted oldest entry: %s", self.name, oldest_key)

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if found."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all entries. Returns count of cleared entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def cleanup(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        with self._lock:
            now = time.time()
            expired_keys = [k for k, (_, exp) in self._cache.items() if exp < now]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __getitem__(self, key: str) -> Any:
        """Dict-style get. Raises KeyError if not found or expired."""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """Dict-style set using default TTL."""
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        """Dict-style delete. Raises KeyError if not found."""
        if not self.delete(key):
            raise KeyError(key)

    def keys(self) -> list[str]:
        """List all keys (for cache invalidation)."""
        with self._lock:
            return list(self._cache.keys())

    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
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
                "utilization_percent": round(
                    len(self._cache) / self.max_size * 100, 2
                ) if self.max_size > 0 else 0,
            }
