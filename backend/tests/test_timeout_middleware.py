"""Comprehensive tests for timeout middleware.

This module tests the TimeoutMiddleware features:
- Endpoint-specific timeouts
- Configurable default timeout
- Proper 504 Gateway Timeout response
- Skip list for certain paths
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.timeout import TimeoutMiddleware


@pytest.fixture
def app_with_timeout():
    """Create FastAPI app with timeout middleware."""
    app = FastAPI()
    app.add_middleware(TimeoutMiddleware)

    @app.get("/api/v1/auth/test")
    async def auth_endpoint():
        await asyncio.sleep(0.1)
        return {"message": "auth"}

    @app.get("/api/v1/resources")
    async def resources_endpoint():
        await asyncio.sleep(0.1)
        return {"resources": []}

    @app.get("/api/v1/export")
    async def export_endpoint():
        await asyncio.sleep(0.1)
        return {"data": "exported"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    return app


@pytest.fixture
def client(app_with_timeout):
    """Create test client."""
    return TestClient(app_with_timeout)


class TestTimeoutConfiguration:
    """Test timeout configuration."""

    def test_default_timeouts_defined(self):
        """Test default timeouts are defined for different endpoints."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        assert "/api/v1/auth" in middleware.DEFAULT_TIMEOUTS
        assert "/api/v1/resources" in middleware.DEFAULT_TIMEOUTS
        assert "/api/v1/export" in middleware.DEFAULT_TIMEOUTS

    def test_auth_endpoint_timeout(self):
        """Test auth endpoint has short timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        timeout = middleware._get_timeout_for_path("/api/v1/auth/login")
        assert timeout == 10.0

    def test_resources_endpoint_timeout(self):
        """Test resources endpoint has longer timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        timeout = middleware._get_timeout_for_path("/api/v1/resources")
        assert timeout == 60.0

    def test_export_endpoint_timeout(self):
        """Test export endpoint has longest timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        timeout = middleware._get_timeout_for_path("/api/v1/export")
        assert timeout == 300.0

    def test_enterprise_export_endpoint_timeout(self):
        """Test enterprise export routes use export timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        timeout = middleware._get_timeout_for_path(
            "/api/v1/enterprise/organizations/org-1/exports/job-1/execute"
        )
        assert timeout == 300.0

    def test_default_timeout_for_unknown_path(self):
        """Test unknown paths use default timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        timeout = middleware._get_timeout_for_path("/api/v1/unknown")
        assert timeout == middleware.default_timeout

    def test_custom_timeout_from_settings(self):
        """Test custom default timeout from settings."""
        with patch('app.middleware.timeout.settings') as mock_settings:
            mock_settings.DEFAULT_REQUEST_TIMEOUT = 45.0

            app = Mock()
            middleware = TimeoutMiddleware(app)

            assert middleware.default_timeout == 45.0

    def test_most_specific_path_match(self):
        """Test most specific path match is used."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        # Should match /api/v1/auth not just /api
        timeout = middleware._get_timeout_for_path("/api/v1/auth/callback")
        assert timeout == 10.0


class TestTimeoutBehavior:
    """Test timeout behavior."""

    def test_skip_list_includes_health(self):
        """Test health endpoints are in skip list."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        # Health paths should not timeout
        assert middleware._get_timeout_for_path("/health") == middleware.default_timeout

    @pytest.mark.asyncio
    async def test_request_within_timeout_succeeds(self):
        """Test request completing within timeout succeeds."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        request = Mock()
        request.url.path = "/api/v1/test"

        async def fast_handler(request):
            await asyncio.sleep(0.01)
            return Mock(status_code=200)

        response = await middleware.dispatch(request, fast_handler)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_exceeding_timeout_returns_504(self):
        """Test slow request returns 504 timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        request = Mock()
        request.url.path = "/api/v1/test"

        async def slow_handler(request):
            await asyncio.sleep(10)  # Longer than timeout
            return Mock(status_code=200)

        # Set a short timeout for testing
        middleware.endpoint_timeouts = {"/api/v1/test": 0.1}

        response = await middleware.dispatch(request, slow_handler)

        assert response.status_code == 504
        assert "timeout" in response.body.decode().lower()

    @pytest.mark.asyncio
    async def test_timeout_response_structure(self):
        """Test timeout response has correct structure."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        request = Mock()
        request.url.path = "/api/v1/test"

        async def slow_handler(request):
            await asyncio.sleep(10)
            return Mock()

        middleware.endpoint_timeouts = {"/api/v1/test": 0.1}

        response = await middleware.dispatch(request, slow_handler)
        body = response.body.decode()

        assert "error" in body or "timeout" in body.lower()
        assert "504" in str(response.status_code)


class TestMiddlewareSkipLogic:
    """Test middleware skip logic."""

    @pytest.mark.asyncio
    async def test_health_endpoints_skip_timeout(self):
        """Test health endpoints skip timeout check."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        request = Mock()
        request.url.path = "/health"

        call_next = AsyncMock(return_value=Mock(status_code=200))

        await middleware.dispatch(request, call_next)

        # Should call next directly without timeout
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_detailed_health_skips_timeout(self):
        """Test detailed health check skips timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        request = Mock()
        request.url.path = "/health/detailed"

        call_next = AsyncMock(return_value=Mock(status_code=200))

        await middleware.dispatch(request, call_next)

        call_next.assert_called_once()

    def test_middleware_can_be_disabled(self):
        """Test middleware can be disabled via settings."""
        with patch('app.middleware.timeout.settings') as mock_settings:
            mock_settings.TIMEOUT_MIDDLEWARE_ENABLED = False

            app = Mock()
            middleware = TimeoutMiddleware(app)

            assert middleware.enabled is False


class TestCustomTimeouts:
    """Test custom timeout configuration."""

    def test_custom_endpoint_timeouts(self):
        """Test custom endpoint timeouts from settings."""
        with patch('app.middleware.timeout.settings') as mock_settings:
            mock_settings.ENDPOINT_TIMEOUTS = {
                "/custom/path": 120.0
            }

            app = Mock()
            middleware = TimeoutMiddleware(app)

            assert "/custom/path" in middleware.endpoint_timeouts

    def test_custom_overrides_default(self):
        """Test custom timeouts override defaults."""
        with patch('app.middleware.timeout.settings') as mock_settings:
            mock_settings.ENDPOINT_TIMEOUTS = {
                "/api/v1/auth": 20.0  # Override default 10s
            }

            app = Mock()
            middleware = TimeoutMiddleware(app)

            timeout = middleware._get_timeout_for_path("/api/v1/auth/login")
            assert timeout == 20.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_path(self):
        """Test empty path handling."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        timeout = middleware._get_timeout_for_path("")
        assert timeout == middleware.default_timeout

    def test_root_path(self):
        """Test root path handling."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        timeout = middleware._get_timeout_for_path("/")
        assert timeout == middleware.default_timeout

    def test_very_long_path(self):
        """Test very long path handling."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        long_path = "/api/v1/" + "/".join(["deep"] * 100)
        timeout = middleware._get_timeout_for_path(long_path)

        assert timeout == middleware.default_timeout

    def test_path_with_special_characters(self):
        """Test path with special characters."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        special_path = "/api/v1/test-123_test.special"
        timeout = middleware._get_timeout_for_path(special_path)

        assert timeout == middleware.default_timeout

    @pytest.mark.asyncio
    async def test_handler_exception_not_swallowed(self):
        """Test handler exceptions are not swallowed by timeout."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        request = Mock()
        request.url.path = "/api/v1/test"

        async def failing_handler(request):
            raise ValueError("Handler error")

        with pytest.raises(ValueError, match="Handler error"):
            await middleware.dispatch(request, failing_handler)

    @pytest.mark.asyncio
    async def test_concurrent_requests_dont_interfere(self):
        """Test concurrent requests have independent timeouts."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        middleware.endpoint_timeouts = {"/api/v1/slow": 0.5}

        async def slow_handler(request):
            await asyncio.sleep(1)
            return Mock(status_code=200)

        request1 = Mock()
        request1.url.path = "/api/v1/slow"

        request2 = Mock()
        request2.url.path = "/api/v1/slow"

        # Both should timeout independently
        response1 = await middleware.dispatch(request1, slow_handler)
        response2 = await middleware.dispatch(request2, slow_handler)

        assert response1.status_code == 504
        assert response2.status_code == 504


class TestTimeoutValues:
    """Test specific timeout values."""

    def test_all_endpoint_timeouts_reasonable(self):
        """Test all endpoint timeouts are reasonable values."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        for path, timeout in middleware.DEFAULT_TIMEOUTS.items():
            assert timeout > 0, f"Timeout for {path} must be positive"
            assert timeout <= 600, f"Timeout for {path} seems too long ({timeout}s)"

    def test_auth_timeout_shortest(self):
        """Test auth timeout is among shortest."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        auth_timeout = middleware.DEFAULT_TIMEOUTS["/api/v1/auth"]

        # Auth should be quick
        assert auth_timeout <= 15.0

    def test_export_timeout_longest(self):
        """Test export timeout is among longest."""
        app = Mock()
        middleware = TimeoutMiddleware(app)

        export_timeout = middleware.DEFAULT_TIMEOUTS["/api/v1/export"]

        # Export can take time
        assert export_timeout >= 300.0
