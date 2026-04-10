"""Request timeout middleware to prevent resource exhaustion."""

import asyncio
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import settings


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Enforce request timeouts to prevent resource exhaustion."""

    # Default timeout for different endpoint types
    DEFAULT_TIMEOUTS = {
        "/api/v1/auth": 10.0,
        "/api/v1/organizations": 10.0,
        "/api/v1/pools": 15.0,
        "/api/v1/expenses": 90.0,  # Cost data can take longer - multiple CSP API calls
        "/api/v1/resources": 60.0,
        "/api/v1/recommendations": 60.0,  # Can fetch from multiple CSPs
        "/api/v1/rules": 15.0,
        "/api/v1/cloud-accounts": 45.0,  # Live data fetching timeout
        "/api/v1/export": 300.0,  # Exports can take longer
        "/api/v1/scheduler": 30.0,
        "/api/v1/users": 15.0,
        "/api/v1/rbac": 15.0,
    }

    def __init__(
        self,
        app: ASGIApp,
        default_timeout: Optional[float] = None
    ):
        super().__init__(app)
        self.default_timeout = default_timeout or getattr(
            settings, "DEFAULT_REQUEST_TIMEOUT", 30.0
        )
        self.enabled = getattr(settings, "TIMEOUT_MIDDLEWARE_ENABLED", True)

        # Allow custom timeouts via settings
        custom_timeouts = getattr(settings, "ENDPOINT_TIMEOUTS", {})
        self.endpoint_timeouts = {**self.DEFAULT_TIMEOUTS, **custom_timeouts}

    def _get_timeout_for_path(self, path: str) -> float:
        """Get appropriate timeout for endpoint."""
        # Strip query string for path matching
        clean_path = path.split("?")[0]

        if clean_path.startswith("/api/v1/resources"):
            return 60.0

        # Enterprise export routes are nested under /api/v1/enterprise but should
        # use the export timeout budget.
        if clean_path.startswith("/api/v1/enterprise") and "/exports" in clean_path:
            return self.endpoint_timeouts.get("/api/v1/export", 300.0)

        # Check for special nested paths first (organizations/{id}/expenses pattern)
        # These need to be checked before generic /organizations prefix
        path_parts = clean_path.split('/')

        # Check for /api/v1/organizations/{org_id}/expenses pattern
        if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "expenses":
            return 90.0

        # Check for /api/v1/organizations/{org_id}/resources pattern
        if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "resources":
            return 90.0

        # Check for /api/v1/organizations/{org_id}/recommendations pattern
        if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "recommendations":
            return 90.0

        # Check for /api/v1/organizations/{org_id}/cloud-accounts pattern
        if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "cloud-accounts":
            return 90.0

        # Find the most specific matching prefix for other paths
        matching_prefixes = [
            (prefix, timeout)
            for prefix, timeout in self.endpoint_timeouts.items()
            if clean_path.startswith(prefix)
        ]

        if matching_prefixes:
            # Return the longest (most specific) matching prefix
            return max(matching_prefixes, key=lambda x: len(x[0]))[1]

        return self.default_timeout

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # Skip timeout for certain paths
        if request.url.path in ["/health", "/health/detailed"]:
            return await call_next(request)

        timeout = self._get_timeout_for_path(request.url.path)

        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Request timeout",
                    "detail": f"Request exceeded {timeout} seconds",
                    "code": "REQUEST_TIMEOUT",
                    "suggestion": "Try again later or contact support if the issue persists"
                }
            )
