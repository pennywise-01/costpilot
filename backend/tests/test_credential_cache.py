"""Comprehensive tests for secure credential caching.

This module tests all features of the SecureCredentialCache:
- Two-tier caching (memory + Redis)
- Automatic TTL expiration
- Thread-safe with asyncio locks
- Cache invalidation per account or all
- Cache statistics tracking
"""

import pytest
import asyncio
import json
from datetime import timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.cloud_accounts.credential_cache import (
    SecureCredentialCache,
    get_credential_cache,
)
from app.shared.utils.time import utc_now


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.scan = AsyncMock(return_value=(0, []))
    return redis


@pytest.fixture
def cache(mock_redis):
    """Create a credential cache with mocked Redis."""
    return SecureCredentialCache(redis_client=mock_redis, ttl_seconds=300)


@pytest.fixture
def memory_only_cache():
    """Create a memory-only credential cache."""
    return SecureCredentialCache(redis_client=None, ttl_seconds=300)


@pytest.fixture
def sample_credentials():
    """Create sample credentials."""
    return {
        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1"
    }


class TestCacheKeyGeneration:
    """Test cache key generation."""

    def test_cache_key_is_deterministic(self, cache):
        """Test same account ID produces same cache key."""
        key1 = cache._get_cache_key("account-123")
        key2 = cache._get_cache_key("account-123")

        assert key1 == key2

    def test_different_accounts_different_keys(self, cache):
        """Test different account IDs produce different cache keys."""
        key1 = cache._get_cache_key("account-123")
        key2 = cache._get_cache_key("account-456")

        assert key1 != key2

    def test_cache_key_is_hash(self, cache):
        """Test cache key is a hash (hex string)."""
        key = cache._get_cache_key("account-123")

        # Should be a hex string
        assert all(c in '0123456789abcdef' for c in key)

    def test_cache_key_includes_prefix(self, cache):
        """Test cache key includes 'cred:' prefix in hash."""
        # Different prefixes should produce different hashes
        key1 = cache._get_cache_key("account-123")

        # Manually compute expected key
        import hashlib
        expected = hashlib.sha256("cred:account-123".encode()).hexdigest()

        assert key1 == expected


class TestMemoryCache:
    """Test in-memory caching."""

    @pytest.mark.asyncio
    async def test_credentials_cached_in_memory(self, memory_only_cache, sample_credentials):
        """Test credentials are cached in memory after first retrieval."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # First call - should decrypt
            creds1 = await memory_only_cache.get_credentials("account-123", "encrypted-data")

            # Second call - should use cache
            creds2 = await memory_only_cache.get_credentials("account-123", "encrypted-data")

            # Decrypt should only be called once
            assert mock_decrypt.call_count == 1
            assert creds1 == sample_credentials
            assert creds2 == sample_credentials

    @pytest.mark.asyncio
    async def test_memory_cache_expires(self, memory_only_cache, sample_credentials):
        """Test memory cache entries expire after TTL."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # Set very short TTL for both memory and Redis
            memory_only_cache._memory_ttl_seconds = 0
            memory_only_cache._ttl_seconds = 0

            # First call
            await memory_only_cache.get_credentials("account-123", "encrypted-data")

            # Wait a tiny bit
            await asyncio.sleep(0.1)

            # Second call - should decrypt again (cache expired)
            await memory_only_cache.get_credentials("account-123", "encrypted-data")

            # Decrypt should be called twice
            assert mock_decrypt.call_count == 2

    @pytest.mark.asyncio
    async def test_different_accounts_separate_cache(self, memory_only_cache, sample_credentials):
        """Test different accounts have separate cache entries."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.side_effect = [
                json.dumps({"key": "account1"}),
                json.dumps({"key": "account2"}),
            ]

            creds1 = await memory_only_cache.get_credentials("account-1", "encrypted-1")
            creds2 = await memory_only_cache.get_credentials("account-2", "encrypted-2")

            assert creds1 == {"key": "account1"}
            assert creds2 == {"key": "account2"}


class TestRedisCache:
    """Test Redis caching."""

    @pytest.mark.asyncio
    async def test_credentials_stored_in_redis(self, cache, mock_redis, sample_credentials):
        """Test credentials are stored in Redis with encryption."""
        with patch('app.shared.key_rotation.encrypt') as mock_encrypt:
            mock_encrypt.return_value = "encrypted-value"

            await cache._cache_credentials("test-key", sample_credentials)

            # Should store encrypted in Redis
            assert mock_redis.setex.called
            mock_encrypt.assert_called_once_with(json.dumps(sample_credentials))

    @pytest.mark.asyncio
    async def test_redis_cache_hit(self, cache, mock_redis, sample_credentials):
        """Test Redis cache hit returns cached credentials."""
        # Mock Redis to return encrypted value
        mock_redis.get.return_value = "encrypted-value"

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            creds = await cache.get_credentials("account-123", "encrypted-data")

            # Should have called decrypt to decrypt the Redis value
            assert mock_decrypt.called
            assert creds == sample_credentials

    @pytest.mark.asyncio
    async def test_redis_cache_populates_memory(self, cache, mock_redis, sample_credentials):
        """Test Redis cache hit populates memory cache."""
        mock_redis.get.return_value = "encrypted-value"

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # First call - from Redis
            await cache.get_credentials("account-123", "encrypted-data")

            # Second call - should use memory cache
            mock_redis.get.reset_mock()
            creds = await cache.get_credentials("account-123", "encrypted-data")

            # Should not call Redis again
            assert not mock_redis.get.called
            assert creds == sample_credentials

    @pytest.mark.asyncio
    async def test_redis_error_fallback_to_decrypt(self, cache, mock_redis, sample_credentials):
        """Test Redis error falls back to decryption."""
        mock_redis.get.side_effect = Exception("Redis error")

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            creds = await cache.get_credentials("account-123", "encrypted-data")

            assert creds == sample_credentials

    @pytest.mark.asyncio
    async def test_redis_store_error_ignored(self, cache, mock_redis, sample_credentials):
        """Test Redis store error is ignored."""
        mock_redis.setex.side_effect = Exception("Redis error")

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # Should not raise exception
            creds = await cache.get_credentials("account-123", "encrypted-data")
            assert creds == sample_credentials


class TestCacheInvalidation:
    """Test cache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_single_account_memory(self, memory_only_cache, sample_credentials):
        """Test invalidating a single account from memory cache."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # Cache credentials
            await memory_only_cache.get_credentials("account-123", "encrypted-data")

            # Invalidate
            result = await memory_only_cache.invalidate("account-123")
            assert result is True

            # Should decrypt again
            await memory_only_cache.get_credentials("account-123", "encrypted-data")
            assert mock_decrypt.call_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_single_account_redis(self, cache, mock_redis):
        """Test invalidating a single account from Redis."""
        result = await cache.invalidate("account-123")

        assert result is True
        assert mock_redis.delete.called

    @pytest.mark.asyncio
    async def test_invalidate_all_memory(self, memory_only_cache, sample_credentials):
        """Test invalidating all entries from memory cache."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # Cache multiple accounts
            await memory_only_cache.get_credentials("account-1", "encrypted-1")
            await memory_only_cache.get_credentials("account-2", "encrypted-2")

            # Invalidate all
            count = await memory_only_cache.invalidate_all()

            assert count == 2
            assert len(memory_only_cache._memory_cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_all_redis(self, cache, mock_redis):
        """Test invalidating all entries from Redis."""
        mock_redis.scan.side_effect = [
            (0, [b"creds:key1", b"creds:key2"]),
        ]

        count = await cache.invalidate_all()

        assert count == 0  # Memory count (Redis keys not counted)
        assert mock_redis.delete.called

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_account(self, memory_only_cache):
        """Test invalidating non-existent account returns False."""
        result = await memory_only_cache.invalidate("nonexistent")
        assert result is False


class TestCacheStatistics:
    """Test cache statistics."""

    @pytest.mark.asyncio
    async def test_stats_returns_expected_fields(self, cache, sample_credentials):
        """Test stats returns expected fields."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)
            await cache.get_credentials("account-123", "encrypted-data")

        stats = cache.get_stats()

        assert "memory_entries" in stats
        assert "valid_entries" in stats
        assert "expired_entries" in stats
        assert "ttl_seconds" in stats
        assert "redis_enabled" in stats

    @pytest.mark.asyncio
    async def test_stats_counts_valid_entries(self, memory_only_cache, sample_credentials):
        """Test stats correctly counts valid entries."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)
            await memory_only_cache.get_credentials("account-123", "encrypted-data")

        stats = memory_only_cache.get_stats()

        assert stats["memory_entries"] == 1
        assert stats["valid_entries"] == 1
        assert stats["expired_entries"] == 0

    @pytest.mark.asyncio
    async def test_stats_counts_expired_entries(self, memory_only_cache, sample_credentials):
        """Test stats correctly counts expired entries."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)
            await memory_only_cache.get_credentials("account-123", "encrypted-data")

        # Manually expire the entry
        cache_key = memory_only_cache._get_cache_key("account-123")
        memory_only_cache._memory_cache[cache_key]["expires_at"] = utc_now() - timedelta(seconds=1)

        stats = memory_only_cache.get_stats()

        assert stats["memory_entries"] == 1
        assert stats["valid_entries"] == 0
        assert stats["expired_entries"] == 1

    def test_stats_redis_enabled(self, cache):
        """Test stats reports Redis enabled."""
        stats = cache.get_stats()
        assert stats["redis_enabled"] is True

    def test_stats_redis_disabled(self, memory_only_cache):
        """Test stats reports Redis disabled."""
        stats = memory_only_cache.get_stats()
        assert stats["redis_enabled"] is False

    def test_stats_ttl_seconds(self, cache):
        """Test stats reports TTL."""
        stats = cache.get_stats()
        assert stats["ttl_seconds"] == 300


class TestThreadSafety:
    """Test thread safety with asyncio locks."""

    @pytest.mark.asyncio
    async def test_concurrent_access_safe(self, memory_only_cache, sample_credentials):
        """Test concurrent access to cache is safe."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # Concurrent calls
            tasks = [
                memory_only_cache.get_credentials("account-123", "encrypted-data")
                for _ in range(10)
            ]
            results = await asyncio.gather(*tasks)

            # All should get same credentials
            assert all(r == sample_credentials for r in results)
            # Decrypt should only be called once
            assert mock_decrypt.call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_invalidate_safe(self, memory_only_cache, sample_credentials):
        """Test concurrent invalidation is safe."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(sample_credentials)

            # Cache first
            await memory_only_cache.get_credentials("account-123", "encrypted-data")

            # Concurrent invalidations
            tasks = [
                memory_only_cache.invalidate("account-123")
                for _ in range(5)
            ]
            results = await asyncio.gather(*tasks)

            # All should succeed without errors (first returns True, rest False)
            assert any(r is True for r in results)  # At least one succeeded
            assert all(isinstance(r, bool) for r in results)  # All returned bool


class TestDecryptionErrors:
    """Test decryption error handling."""

    @pytest.mark.asyncio
    async def test_decrypt_failure_raises_error(self, memory_only_cache):
        """Test decrypt failure raises appropriate error."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.side_effect = Exception("Decryption failed")

            with pytest.raises(Exception, match="Decryption failed"):
                await memory_only_cache.get_credentials("account-123", "invalid-encrypted-data")

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self, memory_only_cache):
        """Test invalid JSON in decrypted data raises error."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = "not-valid-json"

            with pytest.raises(json.JSONDecodeError):
                await memory_only_cache.get_credentials("account-123", "encrypted-data")


class TestGlobalInstance:
    """Test global cache instance."""

    def test_get_credential_cache_singleton(self):
        """Test get_credential_cache returns same instance."""
        # Clear any existing instance
        import app.cloud_accounts.credential_cache as cc
        cc._credential_cache = None

        instance1 = get_credential_cache()
        instance2 = get_credential_cache()

        assert instance1 is instance2

    def test_get_credential_cache_with_redis(self):
        """Test get_credential_cache with Redis client."""
        import app.cloud_accounts.credential_cache as cc
        cc._credential_cache = None

        mock_redis = Mock()
        instance = get_credential_cache(redis_client=mock_redis)

        assert instance._redis is mock_redis


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_credentials(self, memory_only_cache):
        """Test handling of empty credentials."""
        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = "{}"

            creds = await memory_only_cache.get_credentials("account-123", "encrypted-data")
            assert creds == {}

    @pytest.mark.asyncio
    async def test_nested_credentials(self, memory_only_cache):
        """Test handling of nested credentials."""
        nested = {
            "aws": {
                "access_key": "test",
                "secret_key": "secret"
            },
            "settings": {
                "region": "us-east-1"
            }
        }

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(nested)

            creds = await memory_only_cache.get_credentials("account-123", "encrypted-data")
            assert creds == nested

    @pytest.mark.asyncio
    async def test_unicode_credentials(self, memory_only_cache):
        """Test handling of unicode in credentials."""
        unicode_creds = {
            "name": "日本語テスト",
            "description": "Héllo Wörld 🌍"
        }

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(unicode_creds)

            creds = await memory_only_cache.get_credentials("account-123", "encrypted-data")
            assert creds == unicode_creds

    @pytest.mark.asyncio
    async def test_very_large_credentials(self, memory_only_cache):
        """Test handling of very large credential data."""
        large_creds = {
            "data": "A" * 100000  # 100KB of data
        }

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = json.dumps(large_creds)

            creds = await memory_only_cache.get_credentials("account-123", "encrypted-data")
            assert creds == large_creds
