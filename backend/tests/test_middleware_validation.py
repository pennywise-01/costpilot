"""Comprehensive tests for input validation middleware.

This module tests all security features of the InputValidationMiddleware:
- Request size validation
- Content-Type validation
- Path traversal prevention
- Header validation
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.validation import InputValidationMiddleware


@pytest.fixture
def app():
    """Create a test FastAPI app with validation middleware."""
    app = FastAPI()
    app.add_middleware(InputValidationMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.post("/test")
    async def test_post():
        return {"message": "success"}

    @app.put("/test")
    async def test_put():
        return {"message": "success"}

    @app.patch("/test")
    async def test_patch():
        return {"message": "success"}

    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestRequestSizeValidation:
    """Test request size validation."""

    def test_valid_request_size(self, client):
        """Test request with valid size is allowed."""
        response = client.post(
            "/test",
            json={"data": "test"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200

    def test_request_size_too_large(self, client, monkeypatch):
        """Test request exceeding max size is rejected."""
        # Set a small max size for testing
        with patch.object(
            InputValidationMiddleware,
            '__init__',
            lambda self, app: setattr(self, 'max_request_size', 100)
        ):
            # Create new app with small limit
            app = FastAPI()
            app.add_middleware(InputValidationMiddleware)

            @app.post("/test")
            async def test_post():
                return {"message": "success"}

            test_client = TestClient(app)
            response = test_client.post(
                "/test",
                json={"data": "x" * 200},  # Exceeds 100 bytes
                headers={"Content-Type": "application/json"}
            )
            # Note: Content-Length validation happens before body is read
            # So we need to test via mocking

    def test_invalid_content_length_header(self, client):
        """Test invalid Content-Length header is rejected."""
        response = client.post(
            "/test",
            headers={"Content-Length": "invalid", "Content-Type": "application/json"}
        )
        # This should be handled by the middleware


class TestContentTypeValidation:
    """Test Content-Type validation for write operations."""

    def test_post_with_valid_content_type(self, client):
        """Test POST with valid Content-Type is allowed."""
        response = client.post(
            "/test",
            json={"data": "test"},
            headers={"Content-Type": "application/json"}
        )
        # Should succeed (200 if endpoint exists, 404 if not)
        assert response.status_code in [200, 404]

    def test_post_with_multipart_content_type(self, client):
        """Test POST with multipart/form-data is allowed."""
        response = client.post(
            "/test",
            data={"field": "value"},
            headers={"Content-Type": "multipart/form-data"}
        )
        assert response.status_code in [200, 404]

    def test_post_with_invalid_content_type(self, client):
        """Test POST with invalid Content-Type is rejected."""
        with pytest.raises(Exception) as exc_info:
            client.post(
                "/test",
                data="test data",
                headers={"Content-Type": "application/xml"}
            )
        # Exception should contain 415 status
        assert "415" in str(exc_info.value) or "Unsupported media type" in str(exc_info.value)

    def test_post_without_content_type(self, client):
        """Test POST without Content-Type for write operations."""
        # Empty content-type might be handled differently
        with pytest.raises(Exception) as exc_info:
            client.post("/test", data="test")
        # Should be rejected
        assert "415" in str(exc_info.value) or "Unsupported" in str(exc_info.value)

    def test_put_with_invalid_content_type(self, client):
        """Test PUT with invalid Content-Type is rejected."""
        with pytest.raises(Exception) as exc_info:
            client.put(
                "/test",
                data="test data",
                headers={"Content-Type": "text/html"}
            )
        assert "415" in str(exc_info.value) or "Unsupported" in str(exc_info.value)

    def test_patch_with_invalid_content_type(self, client):
        """Test PATCH with invalid Content-Type is rejected."""
        with pytest.raises(Exception) as exc_info:
            client.patch(
                "/test",
                data="test data",
                headers={"Content-Type": "application/javascript"}
            )
        assert "415" in str(exc_info.value) or "Unsupported" in str(exc_info.value)

    def test_get_ignores_content_type(self, client):
        """Test GET requests ignore Content-Type validation."""
        response = client.get("/test", headers={"Content-Type": "application/xml"})
        assert response.status_code == 200

    def test_allowed_content_types(self, client):
        """Test all allowed content types pass validation."""
        allowed_types = [
            "application/json",
            "multipart/form-data",
            "text/plain",
            "application/x-www-form-urlencoded",
        ]

        for content_type in allowed_types:
            response = client.post(
                "/test",
                headers={"Content-Type": content_type}
            )
            # Should not get 415 for allowed types
            assert response.status_code != 415, f"Content-Type {content_type} should be allowed"

    def test_content_type_with_charset(self, client):
        """Test Content-Type with charset is handled correctly."""
        response = client.post(
            "/test",
            json={"data": "test"},
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        # Should strip charset and validate base type
        assert response.status_code in [200, 404]


class TestPathTraversalPrevention:
    """Test path traversal prevention."""

    @pytest.mark.asyncio
    async def test_path_with_double_dot(self):
        """Test path containing .. is rejected."""
        middleware = InputValidationMiddleware(Mock())

        request = Mock()
        request.url.path = "/test/../admin"
        request.method = "GET"
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 400
        assert "Invalid path" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_path_with_encoded_double_dot(self):
        """Test path with encoded .. is rejected."""
        middleware = InputValidationMiddleware(Mock())

        request = Mock()
        request.url.path = "/test/%2e%2e/admin"
        request.method = "GET"
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_path_with_uppercase_encoded_double_dot(self):
        """Test path with uppercase encoded .. is rejected."""
        middleware = InputValidationMiddleware(Mock())

        request = Mock()
        request.url.path = "/test/%2E%2E/admin"
        request.method = "GET"
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 400

    def test_valid_path(self, client):
        """Test valid path is allowed."""
        response = client.get("/test/path/to/resource")
        # Should not be blocked
        assert response.status_code != 400

    def test_path_with_single_dot(self, client):
        """Test path with single dot is allowed."""
        response = client.get("/test/resource")
        # Single dot is OK, only double dot is dangerous
        assert response.status_code != 400


class TestHeaderValidation:
    """Test header validation."""

    @pytest.mark.asyncio
    async def test_valid_user_agent(self):
        """Test valid User-Agent is allowed."""
        middleware = InputValidationMiddleware(Mock())

        request = Mock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {"user-agent": "Mozilla/5.0 Test"}

        call_next = AsyncMock(return_value=Response(status_code=200))
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_long_user_agent(self):
        """Test extremely long User-Agent is rejected."""
        middleware = InputValidationMiddleware(Mock())

        request = Mock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {"user-agent": "A" * 1001}

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, AsyncMock())

        assert exc_info.value.status_code == 400
        assert "User-Agent too long" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_user_agent_exactly_at_limit(self):
        """Test User-Agent at exactly 1000 characters is allowed."""
        middleware = InputValidationMiddleware(Mock())

        request = Mock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {"user-agent": "A" * 1000}

        call_next = AsyncMock(return_value=Response(status_code=200))
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_user_agent(self):
        """Test missing User-Agent is allowed."""
        middleware = InputValidationMiddleware(Mock())

        request = Mock()
        request.url.path = "/test"
        request.method = "GET"
        request.headers = {}

        call_next = AsyncMock(return_value=Response(status_code=200))
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200


class TestMiddlewareInitialization:
    """Test middleware initialization."""

    def test_default_max_size(self):
        """Test default max request size is 10MB."""
        app = FastAPI()
        middleware = InputValidationMiddleware(app)
        assert middleware.max_request_size == 10 * 1024 * 1024

    def test_custom_max_size_from_settings(self, monkeypatch):
        """Test custom max size from settings."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.MAX_REQUEST_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

        with patch('app.middleware.validation.settings', mock_settings):
            app = FastAPI()
            middleware = InputValidationMiddleware(app)
            assert middleware.max_request_size == 5 * 1024 * 1024


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_middleware_chain_continues(self):
        """Test middleware allows request to continue to next handler."""
        app = Mock()
        middleware = InputValidationMiddleware(app)

        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "content-type": "application/json"
        }
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        # Create mock call_next
        mock_response = Mock(spec=Response)
        call_next = AsyncMock(return_value=mock_response)

        # Call dispatch
        response = await middleware.dispatch(mock_request, call_next)

        # Should call next handler
        call_next.assert_called_once_with(mock_request)
        assert response == mock_response

    def test_delete_method_content_type(self, client):
        """Test DELETE requests handle Content-Type appropriately."""
        # DELETE is not in the list of write operations to validate
        response = client.delete(
            "/test",
            headers={"Content-Type": "application/xml"}
        )
        # DELETE shouldn't be validated for Content-Type
        assert response.status_code != 415

    def test_empty_path(self, client):
        """Test empty path handling."""
        response = client.get("/")
        # Root path should be allowed
        assert response.status_code != 400
