"""Rate limiting middleware with Redis-backed sliding window."""

import hashlib
import time
from enum import Enum
from typing import Optional, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import settings


class RateLimitTier(Enum):
    """Different rate limit tiers for different endpoint types."""
    PUBLIC = {"requests": 30, "window": 60}      # 30/min for public endpoints
    AUTHENTICATED = {"requests": 100, "window": 60}  # 100/min for auth users
    EXPENSIVE = {"requests": 10, "window": 60}   # 10/min for expensive ops
    EXPORT = {"requests": 5, "window": 300}      # 5/5min for exports
    WEBHOOK = {"requests": 1000, "window": 60}   # 1000/min for webhooks


class InMemoryRateLimiter:
    """In-memory rate limiter for development/single-instance deployments."""

    def __init__(self):
        self._requests: dict[str, list[float]] = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def _cleanup_old_entries(self):
        """Remove expired entries to prevent memory growth."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - 3600  # Keep 1 hour of history
        for key in list(self._requests.keys()):
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]
            if not self._requests[key]:
                del self._requests[key]

        self._last_cleanup = now

    async def is_allowed(
        self,
        key: str,
        tier: RateLimitTier,
        burst: int = 0
    ) -> tuple[bool, dict]:
        """Check if request is allowed using sliding window."""
        self._cleanup_old_entries()

        now = time.time()
        window = tier.value["window"]
        limit = tier.value["requests"] + burst

        # Get or create request list for this key
        if key not in self._requests:
            self._requests[key] = []

        # Remove old entries outside window
        self._requests[key] = [t for t in self._requests[key] if now - t < window]

        # Check if limit exceeded
        current_count = len(self._requests[key])
        allowed = current_count < limit

        # Add current request timestamp
        self._requests[key].append(now)

        # Calculate retry after
        retry_after = 0
        if not allowed and self._requests[key]:
            oldest = min(self._requests[key])
            retry_after = int(oldest + window - now)

        return allowed, {
            "limit": limit,
            "remaining": max(0, limit - current_count - 1),
            "reset": int(now + window),
            "retry_after": max(0, retry_after)
        }


class RedisRateLimiter:
    """Distributed rate limiting using Redis with sliding window."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client

    async def is_allowed(
        self,
        key: str,
        tier: RateLimitTier,
        burst: int = 0
    ) -> tuple[bool, dict]:
        """Check if request is allowed using Redis sorted sets (sliding window)."""
        now = time.time()
        window = tier.value["window"]
        limit = tier.value["requests"] + burst
        window_start = now - window

        try:
            pipe = self.redis.pipeline()
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Set expiry on the key
            pipe.expire(key, window + 1)
            # Count requests in window
            pipe.zcard(key)

            results = await pipe.execute()
            request_count = results[3]

            allowed = request_count <= limit

            # Calculate retry_after if not allowed
            retry_after = 0
            if not allowed:
                oldest = await self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = max(1, int(oldest[0][1] + window - now))

            remaining = max(0, limit - request_count) if allowed else 0

            return allowed, {
                "limit": limit,
                "remaining": remaining,
                "reset": int(now + window),
                "retry_after": retry_after
            }
        except Exception:
            # If Redis fails, raise to trigger fallback
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limiting based on endpoint and user.

    Uses Redis-backed distributed rate limiting when Redis is available,
    falling back to in-memory limiting for single-instance deployments.
    """

    def __init__(self, app: ASGIApp, redis_client: Optional[Any] = None):
        super().__init__(app)
        self._redis_client = redis_client
        self._memory_limiter = InMemoryRateLimiter()
        self.enabled = getattr(settings, "RATE_LIMITING_ENABLED", True)

    def _get_redis_client(self) -> Optional[Any]:
        """Get Redis client from constructor parameter."""
        return self._redis_client

    async def _get_limiter_for_request(self, request: Request):
        """Determine which rate limiter to use for this request.

        Returns (limiter, is_redis) tuple.
        """
        redis_client = self._get_redis_client()

        # Also check app.state.redis for dynamically configured Redis
        if redis_client is None:
            redis_client = getattr(request.app.state, "redis", None)

        if redis_client is not None:
            return RedisRateLimiter(redis_client), True

        return self._memory_limiter, False

    def _get_tier_for_path(self, path: str) -> RateLimitTier:
        """Determine rate limit tier based on endpoint path."""
        if "/export" in path:
            return RateLimitTier.EXPORT
        elif "/webhook" in path:
            return RateLimitTier.WEBHOOK
        elif any(x in path for x in ["/recommendations", "/csp/", "/discover"]):
            return RateLimitTier.EXPENSIVE
        elif path.startswith("/api/v1/auth"):
            return RateLimitTier.PUBLIC
        else:
            return RateLimitTier.AUTHENTICATED

    def _get_tier_for_request(self, request: Request) -> RateLimitTier:
        """Determine rate limit tier with request-method aware overrides."""
        tier = self._get_tier_for_path(request.url.path)

        # Export reads can be frequent in UI polling/refresh flows and should not
        # consume the stricter export-write budget used for job execution actions.
        if tier == RateLimitTier.EXPORT and request.method in {"GET", "HEAD", "OPTIONS"}:
            return RateLimitTier.AUTHENTICATED

        return tier

    def _generate_key(self, request: Request, tier: RateLimitTier | None = None) -> str:
        """Generate rate limit key from request."""
        # Get identifier (user ID from token or IP address)
        identifier = "anonymous"
        user_id = getattr(request.state, "user_id", None)

        # Try to get user ID from request state (set by auth middleware)
        if user_id:
            identifier = f"user:{user_id}"
        else:
            session_id = None
            if hasattr(request, "cookies") and request.cookies is not None:
                try:
                    session_id = request.cookies.get("session_id")
                except Exception:
                    session_id = None

            # Session-aware keying prevents all users behind a shared proxy/container
            # IP from contending on one global bucket.
            if isinstance(session_id, str) and session_id:
                session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
                identifier = f"session:{session_hash}"
            elif request.client and request.client.host:
                identifier = f"ip:{request.client.host}"

        # Include path for per-endpoint limiting
        resolved_tier = tier or self._get_tier_for_path(request.url.path)
        method = str(getattr(request, "method", "GET")).upper()
        path_key = request.url.path.rstrip("/") or "/"

        return f"ratelimit:{resolved_tier.name}:{identifier}:{method}:{path_key}"

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            response = await call_next(request)
            return response

        # Skip rate limiting for certain paths
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            response = await call_next(request)
            return response

        # Determine rate limit tier
        tier = self._get_tier_for_request(request)

        # Generate rate limit key
        key = self._generate_key(request, tier=tier)

        # Determine which limiter to use (Redis if available, fallback to in-memory)
        limiter, _ = await self._get_limiter_for_request(request)

        try:
            allowed, headers = await limiter.is_allowed(key, tier)
        except Exception:
            # Redis failed - fall back to in-memory rate limiting
            limiter = self._memory_limiter
            allowed, headers = await limiter.is_allowed(key, tier)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "Retry-After": str(headers["retry_after"]),
                    "X-RateLimit-Limit": str(headers["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(headers["reset"])
                }
            )

        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(headers["limit"])
        response.headers["X-RateLimit-Remaining"] = str(headers["remaining"])
        response.headers["X-RateLimit-Reset"] = str(headers["reset"])

        return response
