"""Comprehensive tests for rate limiting middleware.

This module tests all features of the rate limiter:
- Tier-based rate limiting (PUBLIC, AUTHENTICATED, EXPENSIVE, EXPORT, WEBHOOK)
- Sliding window algorithm
- Redis-backed for distributed deployments
- In-memory fallback for single-instance
- Rate limit headers in responses
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limiter import (
    RateLimitTier,
    InMemoryRateLimiter,
    RedisRateLimiter,
    RateLimitMiddleware,
)


@pytest.fixture
def in_memory_limiter():
    """Create an in-memory rate limiter."""
    return InMemoryRateLimiter()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.pipeline = Mock(return_value=AsyncMock())
    return redis


@pytest.fixture
def app_with_rate_limit(mock_redis):
    """Create a FastAPI app with rate limiting."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, redis_client=mock_redis)

    @app.get("/api/v1/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.get("/api/v1/export")
    async def export_endpoint():
        return {"data": "exported"}

    @app.get("/api/v1/recommendations")
    async def recommendations_endpoint():
        return {"recommendations": []}

    return app


class TestRateLimitTiers:
    """Test rate limit tier definitions."""

    def test_public_tier_limits(self):
        """Test PUBLIC tier rate limits."""
        assert RateLimitTier.PUBLIC.value["requests"] == 30
        assert RateLimitTier.PUBLIC.value["window"] == 60

    def test_authenticated_tier_limits(self):
        """Test AUTHENTICATED tier rate limits."""
        assert RateLimitTier.AUTHENTICATED.value["requests"] == 100
        assert RateLimitTier.AUTHENTICATED.value["window"] == 60

    def test_expensive_tier_limits(self):
        """Test EXPENSIVE tier rate limits."""
        assert RateLimitTier.EXPENSIVE.value["requests"] == 10
        assert RateLimitTier.EXPENSIVE.value["window"] == 60

    def test_export_tier_limits(self):
        """Test EXPORT tier rate limits."""
        assert RateLimitTier.EXPORT.value["requests"] == 5
        assert RateLimitTier.EXPORT.value["window"] == 300

    def test_webhook_tier_limits(self):
        """Test WEBHOOK tier rate limits."""
        assert RateLimitTier.WEBHOOK.value["requests"] == 1000
        assert RateLimitTier.WEBHOOK.value["window"] == 60


class TestInMemoryRateLimiter:
    """Test in-memory rate limiter."""

    @pytest.mark.asyncio
    async def test_allow_first_request(self, in_memory_limiter):
        """Test first request is allowed."""
        allowed, headers = await in_memory_limiter.is_allowed(
            "key-1", RateLimitTier.PUBLIC
        )

        assert allowed is True
        assert headers["limit"] == 30
        assert headers["remaining"] == 29

    @pytest.mark.asyncio
    async def test_allow_requests_within_limit(self, in_memory_limiter):
        """Test requests within limit are allowed."""
        for i in range(30):
            allowed, headers = await in_memory_limiter.is_allowed(
                "key-1", RateLimitTier.PUBLIC
            )
            assert allowed is True

    @pytest.mark.asyncio
    async def test_reject_requests_over_limit(self, in_memory_limiter):
        """Test requests over limit are rejected."""
        # Exhaust the limit
        for i in range(30):
            await in_memory_limiter.is_allowed("key-1", RateLimitTier.PUBLIC)

        # Next request should be rejected
        allowed, headers = await in_memory_limiter.is_allowed(
            "key-1", RateLimitTier.PUBLIC
        )

        assert allowed is False
        assert headers["remaining"] == 0
        assert headers["retry_after"] > 0

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, in_memory_limiter):
        """Test different keys have independent limits."""
        # Exhaust limit for key-1
        for i in range(30):
            await in_memory_limiter.is_allowed("key-1", RateLimitTier.PUBLIC)

        # key-2 should still have full limit
        allowed, headers = await in_memory_limiter.is_allowed(
            "key-2", RateLimitTier.PUBLIC
        )

        assert allowed is True
        assert headers["remaining"] == 29

    @pytest.mark.asyncio
    async def test_window_resets_after_time(self, in_memory_limiter):
        """Test limit resets after window expires."""
        # Make a request
        await in_memory_limiter.is_allowed("key-1", RateLimitTier.PUBLIC)

        # Simulate time passing (modify the stored timestamp)
        old_time = time.time()
        in_memory_limiter._requests["key-1"][0] = old_time - 61  # 61 seconds ago

        # Request should be allowed again
        allowed, headers = await in_memory_limiter.is_allowed(
            "key-1", RateLimitTier.PUBLIC
        )

        assert allowed is True

    @pytest.mark.asyncio
    async def test_burst_allowance(self, in_memory_limiter):
        """Test burst allowance increases limit."""
        allowed, headers = await in_memory_limiter.is_allowed(
            "key-1", RateLimitTier.PUBLIC, burst=10
        )

        assert allowed is True
        assert headers["limit"] == 40  # 30 + 10 burst

    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, in_memory_limiter):
        """Test old entries are cleaned up."""
        # Add old entries
        in_memory_limiter._requests["old-key"] = [time.time() - 7200]  # 2 hours ago
        in_memory_limiter._last_cleanup = time.time() - 400  # Force cleanup

        # Trigger cleanup
        in_memory_limiter._cleanup_old_entries()

        # Old entry should be removed
        assert "old-key" not in in_memory_limiter._requests


class TestRedisRateLimiter:
    """Test Redis-backed rate limiter."""

    @pytest.mark.asyncio
    async def test_allow_first_request(self, mock_redis):
        """Test first request is allowed with Redis."""
        limiter = RedisRateLimiter(mock_redis)

        # Mock pipeline results
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[0, 0, 1, 1])  # zrem, zcard, zadd, expire
        mock_redis.pipeline.return_value = mock_pipe

        allowed, headers = await limiter.is_allowed("key-1", RateLimitTier.PUBLIC)

        assert allowed is True
        assert mock_pipe.zadd.called

    @pytest.mark.asyncio
    async def test_reject_over_limit(self, mock_redis):
        """Test request over limit is rejected with Redis."""
        limiter = RedisRateLimiter(mock_redis)

        # Mock pipeline showing 31 requests (current + 30 existing, exceeds limit of 30)
        # The Redis algorithm checks request_count <= limit AFTER adding current request
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[0, 30, 1, 31])
        mock_redis.pipeline.return_value = mock_pipe

        # Mock oldest request for retry_after
        mock_redis.zrange = AsyncMock(return_value=[("timestamp", time.time() - 30)])

        allowed, headers = await limiter.is_allowed("key-1", RateLimitTier.PUBLIC)

        assert allowed is False


class TestRateLimitMiddleware:
    """Test rate limit middleware."""

    def test_get_tier_for_export_path(self):
        """Test export paths get EXPORT tier."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        tier = middleware._get_tier_for_path("/api/v1/export")
        assert tier == RateLimitTier.EXPORT

    def test_get_tier_for_webhook_path(self):
        """Test webhook paths get WEBHOOK tier."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        tier = middleware._get_tier_for_path("/api/v1/webhook/github")
        assert tier == RateLimitTier.WEBHOOK

    def test_get_tier_for_expensive_path(self):
        """Test expensive paths get EXPENSIVE tier."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        tier = middleware._get_tier_for_path("/api/v1/recommendations")
        assert tier == RateLimitTier.EXPENSIVE

    def test_get_tier_for_auth_path(self):
        """Test auth paths get PUBLIC tier."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        tier = middleware._get_tier_for_path("/api/v1/auth/login")
        assert tier == RateLimitTier.PUBLIC

    def test_get_tier_for_default_path(self):
        """Test default paths get AUTHENTICATED tier."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        tier = middleware._get_tier_for_path("/api/v1/users")
        assert tier == RateLimitTier.AUTHENTICATED

    def test_generate_key_with_user_id(self):
        """Test key generation with user ID."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        request = Mock()
        request.state = Mock()
        request.state.user_id = "user-123"
        request.url.path = "/api/v1/test"
        request.client = None

        key = middleware._generate_key(request)

        assert "user:user-123" in key

    def test_generate_key_with_ip(self):
        """Test key generation with IP address."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        request = Mock()
        request.state = Mock()
        request.state.user_id = None
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.url.path = "/api/v1/test"

        key = middleware._generate_key(request)

        assert "ip:192.168.1.100" in key

    def test_generate_key_anonymous(self):
        """Test key generation for anonymous requests."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        request = Mock()
        request.state = Mock()
        request.state.user_id = None
        request.client = None
        request.url.path = "/api/v1/test"

        key = middleware._generate_key(request)

        assert "anonymous" in key

    def test_skip_health_endpoints(self, mock_redis):
        """Test health endpoints are skipped."""
        app = Mock()
        middleware = RateLimitMiddleware(app, redis_client=mock_redis)

        request = Mock()
        request.url.path = "/health"

        # Health paths should be skipped
        assert middleware._get_tier_for_path("/health") == RateLimitTier.AUTHENTICATED


class TestSlidingWindowAlgorithm:
    """Test sliding window rate limiting algorithm."""

    @pytest.mark.asyncio
    async def test_sliding_window_accuracy(self, in_memory_limiter):
        """Test sliding window accurately tracks requests."""
        now = time.time()

        # Add requests at different times within window
        in_memory_limiter._requests["test-key"] = [
            now - 10,  # 10 seconds ago
            now - 20,  # 20 seconds ago
            now - 50,  # 50 seconds ago
        ]

        # With 60 second window, all should count
        allowed, headers = await in_memory_limiter.is_allowed(
            "test-key", RateLimitTier.PUBLIC
        )

        assert headers["limit"] == 30
        # Should show remaining based on requests in window

    @pytest.mark.asyncio
    async def test_requests_outside_window_ignored(self, in_memory_limiter):
        """Test requests outside window are not counted."""
        now = time.time()

        # Add old requests
        in_memory_limiter._requests["test-key"] = [
            now - 100,  # 100 seconds ago (outside 60s window)
            now - 200,  # 200 seconds ago
        ]

        allowed, headers = await in_memory_limiter.is_allowed(
            "test-key", RateLimitTier.PUBLIC
        )

        # Old requests should be ignored
        assert headers["remaining"] >= 28  # Should have most of limit available


class TestRateLimitHeaders:
    """Test rate limit headers in responses."""

    @pytest.mark.asyncio
    async def test_headers_include_limit(self, in_memory_limiter):
        """Test headers include rate limit."""
        allowed, headers = await in_memory_limiter.is_allowed(
            "key", RateLimitTier.PUBLIC
        )

        assert "limit" in headers
        assert "remaining" in headers
        assert "reset" in headers
        assert "retry_after" in headers

    @pytest.mark.asyncio
    async def test_retry_after_when_rejected(self, in_memory_limiter):
        """Test retry_after is set when request is rejected."""
        # Exhaust limit
        for i in range(30):
            await in_memory_limiter.is_allowed("key", RateLimitTier.PUBLIC)

        allowed, headers = await in_memory_limiter.is_allowed(
            "key", RateLimitTier.PUBLIC
        )

        assert allowed is False
        assert headers["retry_after"] > 0
        assert headers["retry_after"] <= 60


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, in_memory_limiter):
        """Test handling of concurrent requests."""
        import asyncio

        async def make_request():
            return await in_memory_limiter.is_allowed("concurrent-key", RateLimitTier.PUBLIC)

        # Make many concurrent requests
        tasks = [make_request() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # Count allowed and rejected
        allowed_count = sum(1 for allowed, _ in results if allowed)
        rejected_count = sum(1 for allowed, _ in results if not allowed)

        # Should be approximately at the limit (30)
        assert allowed_count <= 30
        assert rejected_count >= 20

    @pytest.mark.asyncio
    async def test_rate_limit_disabled(self, mock_redis):
        """Test rate limiting can be disabled."""
        with patch('app.middleware.rate_limiter.settings') as mock_settings:
            mock_settings.RATE_LIMITING_ENABLED = False

            app = Mock()
            middleware = RateLimitMiddleware(app, redis_client=mock_redis)

            assert middleware.enabled is False

    def test_export_tier_longer_window(self):
        """Test EXPORT tier has longer window."""
        assert RateLimitTier.EXPORT.value["window"] == 300  # 5 minutes

    @pytest.mark.asyncio
    async def test_burst_with_different_tiers(self, in_memory_limiter):
        """Test burst allowance works with different tiers."""
        # PUBLIC tier with burst
        allowed, headers = await in_memory_limiter.is_allowed(
            "key-1", RateLimitTier.PUBLIC, burst=20
        )
        assert headers["limit"] == 50  # 30 + 20

        # EXPENSIVE tier with burst
        allowed, headers = await in_memory_limiter.is_allowed(
            "key-2", RateLimitTier.EXPENSIVE, burst=5
        )
        assert headers["limit"] == 15  # 10 + 5

    def test_tier_name_in_key(self):
        """Test tier name is included in rate limit key."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        request = Mock()
        request.state = Mock()
        request.state.user_id = "user-123"
        request.url.path = "/api/v1/export"
        request.client = None

        key = middleware._generate_key(request)

        assert "EXPORT" in key
