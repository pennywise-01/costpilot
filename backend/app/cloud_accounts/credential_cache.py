"""Secure credential caching to reduce decryption overhead."""

import asyncio
import hashlib
import json
from datetime import timedelta
from typing import Optional, Any
import logging

from app.shared.key_rotation import KeyRotator
from app.config import settings
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)

# In-memory cache TTL - kept short to limit exposure of decrypted credentials
_MEMORY_TTL_SECONDS = 60


class SecureCredentialCache:
    """Cache decrypted credentials securely with automatic expiration and rotation.
    
    This cache stores decrypted credentials in memory and optionally in Redis
    to avoid repeated decryption operations which can be CPU-intensive.
    """

    def __init__(self, redis_client: Optional[Any] = None, ttl_seconds: int = 300):
        """Initialize credential cache.

        Args:
            redis_client: Optional Redis client for distributed caching
            ttl_seconds: Time-to-live for cached credentials (default: 5 minutes)
        """
        self._memory_cache: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds
        self._redis = redis_client
        self._memory_ttl_seconds = _MEMORY_TTL_SECONDS
        self._key_rotator = KeyRotator(primary_key=settings.ENCRYPTION_KEY)

    def _get_cache_key(self, account_id: str) -> str:
        """Generate secure cache key from account ID."""
        return hashlib.sha256(f"cred:{account_id}".encode()).hexdigest()

    def _cleanup_expired(self) -> int:
        """Remove expired entries from the in-memory cache.

        Returns the number of entries removed. Should be called
        periodically (e.g. on every get_credentials call) to
        prevent unbounded growth from stale entries.
        """
        now = utc_now()
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if v["expires_at"] <= now
        ]
        for k in expired_keys:
            del self._memory_cache[k]
        return len(expired_keys)

    async def get_credentials(
        self,
        account_id: str,
        encrypted_config: str
    ) -> dict[str, Any]:
        """Get cached credentials or decrypt fresh.

        Args:
            account_id: Cloud account ID
            encrypted_config: Encrypted configuration string

        Returns:
            Decrypted credentials dictionary
        """
        cache_key = self._get_cache_key(account_id)

        # Proactively clean up expired entries to prevent unbounded growth
        self._cleanup_expired()

        async with self._lock:
            # Check memory cache first
            cached = self._memory_cache.get(cache_key)
            if cached and cached["expires_at"] > utc_now():
                logger.info(
                    "credential_cache_get",
                    extra={
                        "event": "credential_cache_get",
                        "source": "memory",
                        "account_id": account_id,
                        "cache_key": cache_key,
                    },
                )
                return cached["credentials"]

        # Check Redis cache (distributed)
        if self._redis:
            try:
                redis_cached = await self._redis.get(f"creds:{cache_key}")
                if redis_cached:
                    # Decrypt the Redis-stored credentials
                    decrypted_value = self._key_rotator.decrypt(redis_cached)
                    creds = json.loads(decrypted_value)
                    # Update memory cache
                    async with self._lock:
                        self._memory_cache[cache_key] = {
                            "credentials": creds,
                            "expires_at": utc_now() + timedelta(seconds=self._memory_ttl_seconds)
                        }
                    logger.info(
                        "credential_cache_get",
                        extra={
                            "event": "credential_cache_get",
                            "source": "redis",
                            "account_id": account_id,
                            "cache_key": cache_key,
                        },
                    )
                    return creds
            except Exception as e:
                logger.warning(f"Redis credential cache error: {e}")

        # Decrypt fresh
        try:
            credentials = json.loads(self._key_rotator.decrypt(encrypted_config))
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for account {account_id}: {e}")
            raise

        # Cache the decrypted credentials
        await self._cache_credentials(cache_key, credentials)

        logger.info(
            "credential_cache_get",
            extra={
                "event": "credential_cache_get",
                "source": "decrypted",
                "account_id": account_id,
                "cache_key": cache_key,
            },
        )

        return credentials

    async def _cache_credentials(self, cache_key: str, credentials: dict):
        """Cache credentials in memory and Redis (encrypted)."""
        expires_at = utc_now() + timedelta(seconds=self._memory_ttl_seconds)

        async with self._lock:
            self._memory_cache[cache_key] = {
                "credentials": credentials,
                "expires_at": expires_at,
            }

        # Encrypt and cache in Redis
        if self._redis:
            try:
                encrypted_value = self._key_rotator.encrypt(json.dumps(credentials))
                await self._redis.setex(
                    f"creds:{cache_key}",
                    self._ttl_seconds,
                    encrypted_value,
                )
                logger.info(
                    "credential_cache_set",
                    extra={
                        "event": "credential_cache_set",
                        "cache_key": cache_key,
                        "redis": True,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to cache credentials in Redis: {e}")
        else:
            logger.info(
                "credential_cache_set",
                extra={
                    "event": "credential_cache_set",
                    "cache_key": cache_key,
                    "redis": False,
                },
            )

    async def invalidate(self, account_id: str) -> bool:
        """Invalidate cached credentials for an account.

        Args:
            account_id: Cloud account ID

        Returns:
            True if credentials were invalidated
        """
        cache_key = self._get_cache_key(account_id)
        invalidated = False

        async with self._lock:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                invalidated = True

        if self._redis:
            try:
                await self._redis.delete(f"creds:{cache_key}")
                invalidated = True
            except Exception as e:
                logger.warning(f"Failed to invalidate Redis cache: {e}")

        logger.info(
            "credential_cache_invalidate",
            extra={
                "event": "credential_cache_invalidate",
                "account_id": account_id,
                "cache_key": cache_key,
                "invalidated": invalidated,
            },
        )

        return invalidated

    async def invalidate_all(self) -> int:
        """Invalidate all cached credentials.

        Returns:
            Number of entries invalidated
        """
        async with self._lock:
            count = len(self._memory_cache)
            self._memory_cache.clear()

        redis_invalidated = False
        if self._redis:
            try:
                # This is a simplified approach - in production you might want
                # to use a more targeted deletion strategy
                pattern = "creds:*"
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self._redis.delete(*keys)
                    if cursor == 0:
                        break
                redis_invalidated = True
            except Exception as e:
                logger.warning(f"Failed to invalidate all Redis cache: {e}")

        logger.info(
            "credential_cache_invalidate_all",
            extra={
                "event": "credential_cache_invalidate_all",
                "memory_count": count,
                "redis_invalidated": redis_invalidated,
            },
        )

        return count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        now = utc_now()
        valid_entries = sum(
            1 for v in self._memory_cache.values()
            if v["expires_at"] > now
        )
        expired_entries = len(self._memory_cache) - valid_entries

        return {
            "memory_entries": len(self._memory_cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "ttl_seconds": self._ttl_seconds,
            "redis_enabled": self._redis is not None
        }


# Global cache instance
_credential_cache: Optional[SecureCredentialCache] = None


def get_credential_cache(redis_client: Optional[Any] = None) -> SecureCredentialCache:
    """Get or create global credential cache instance."""
    global _credential_cache
    if _credential_cache is None:
        _credential_cache = SecureCredentialCache(redis_client=redis_client)
        logger.info("SecureCredentialCache singleton initialized (redis=%s)", redis_client is not None)
    return _credential_cache
