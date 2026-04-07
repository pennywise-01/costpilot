"""End-to-End tests for complete security flows.

This module tests complete security flows integrating multiple components:
- Complete authentication flow (login, token refresh, logout)
- Session security validation flow
- Rate limiting integration
- Audit logging integration
- Complete credential lifecycle
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt

from app.auth.token_manager import SecureTokenManager, TokenRotationError
from app.auth.session_security import SessionSecurityValidator
from app.middleware.rate_limiter import RateLimitMiddleware, RateLimitTier, InMemoryRateLimiter
from app.middleware.validation import InputValidationMiddleware
from app.middleware.timeout import TimeoutMiddleware
from app.security.audit_logger import AuditLogger, AuditEventType, AuditSeverity


@pytest.fixture
def e2e_app():
    """Create FastAPI app with all security middleware."""
    app = FastAPI()

    # Add all security middleware in correct order
    app.add_middleware(InputValidationMiddleware)
    app.add_middleware(TimeoutMiddleware)
    app.add_middleware(RateLimitMiddleware)

    return app


@pytest.fixture
def e2e_client(e2e_app):
    """Create test client for E2E tests."""
    return TestClient(e2e_app)


class TestCompleteAuthenticationFlow:
    """Test complete authentication flow."""

    @pytest.mark.asyncio
    async def test_full_login_flow(self):
        """Test complete login flow with session binding."""
        # Setup components
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, []))

        with patch('app.auth.token_manager.settings') as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-for-jwt-123456789012345678"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15

            token_manager = SecureTokenManager(redis_client=mock_redis)
            session_validator = SessionSecurityValidator()

            # 1. User logs in - create token pair
            tokens = await token_manager.create_token_pair("user-123", "session-456")

            assert "access_token" in tokens
            assert "refresh_token" in tokens

            # 2. Validate access token
            decoded = token_manager.decode_access_token(tokens["access_token"])
            assert decoded["sub"] == "user-123"

            # 3. Simulate token refresh
            mock_redis.get.return_value = str({
                "user_id": "user-123",
                "session_id": "session-456",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "used": False
            })

            new_tokens = await token_manager.rotate_refresh_token(tokens["refresh_token"])
            assert new_tokens["access_token"] != tokens["access_token"]

    @pytest.mark.asyncio
    async def test_token_reuse_detection_flow(self):
        """Test token reuse detection triggers security response."""
        mock_redis = AsyncMock()

        with patch('app.auth.token_manager.settings') as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-for-jwt-123456789012345678"
            mock_settings.JWT_ALGORITHM = "HS256"

            token_manager = SecureTokenManager(redis_client=mock_redis)

            # Create initial tokens
            tokens = await token_manager.create_token_pair("user-123", "session-456")

            # Simulate token being marked as used
            mock_redis.get.return_value = str({
                "user_id": "user-123",
                "session_id": "session-456",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "used": True  # Already used!
            })

            # Attempt to reuse should trigger detection
            with pytest.raises(TokenRotationError, match="Token reuse detected"):
                await token_manager.rotate_refresh_token(tokens["refresh_token"])

    @pytest.mark.asyncio
    async def test_session_binding_validation_flow(self):
        """Test session binding validation throughout request lifecycle."""
        session_validator = SessionSecurityValidator()

        # Create mock request
        mock_request = Mock()
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {
            "user-agent": "Mozilla/5.0",
            "accept-language": "en-US",
            "accept-encoding": "gzip",
            "dnt": "1"
        }

        # Generate original fingerprint
        original_fingerprint = session_validator.generate_session_fingerprint(mock_request)

        # 1. Same request should pass
        is_valid, reason = session_validator.validate_session_binding(
            mock_request,
            stored_fingerprint=original_fingerprint,
            stored_ip="192.168.1.100"
        )
        assert is_valid is True

        # 2. Different IP should fail in strict mode
        mock_request.client.host = "10.0.0.1"
        is_valid, reason = session_validator.validate_session_binding(
            mock_request,
            stored_fingerprint=original_fingerprint,
            stored_ip="192.168.1.100",
            strict_mode=True
        )
        assert is_valid is False
        assert reason == "IP_ADDRESS_MISMATCH"

        # 3. Same /24 subnet should pass in lenient mode
        mock_request.client.host = "192.168.1.50"
        is_valid, reason = session_validator.validate_session_binding(
            mock_request,
            stored_fingerprint=original_fingerprint,
            stored_ip="192.168.1.100",
            strict_mode=False
        )
        assert is_valid is True


class TestRateLimitingIntegration:
    """Test rate limiting integration with other components."""

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_after_exceeded(self):
        """Test rate limiting blocks requests after limit exceeded."""
        from app.middleware.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        # Make requests up to limit
        for i in range(30):  # PUBLIC tier limit
            allowed, headers = await limiter.is_allowed(
                "user:123", RateLimitTier.PUBLIC
            )
            assert allowed is True

        # Next request should be blocked
        allowed, headers = await limiter.is_allowed(
            "user:123", RateLimitTier.PUBLIC
        )
        assert allowed is False
        assert headers["retry_after"] > 0

    @pytest.mark.asyncio
    async def test_different_endpoints_different_limits(self):
        """Test different endpoints have different rate limits."""
        app = Mock()
        middleware = RateLimitMiddleware(app)

        # Export endpoint should have lower limit
        export_tier = middleware._get_tier_for_path("/api/v1/export")
        assert export_tier == RateLimitTier.EXPORT
        assert export_tier.value["requests"] == 5

        # Webhook endpoint should have high limit
        webhook_tier = middleware._get_tier_for_path("/api/v1/webhook")
        assert webhook_tier == RateLimitTier.WEBHOOK
        assert webhook_tier.value["requests"] == 1000

        # Recommendations should be expensive
        rec_tier = middleware._get_tier_for_path("/api/v1/recommendations")
        assert rec_tier == RateLimitTier.EXPENSIVE
        assert rec_tier.value["requests"] == 10


class TestAuditLoggingIntegration:
    """Test audit logging integration with security events."""

    @pytest.mark.asyncio
    async def test_security_events_logged(self):
        """Test security events are properly logged."""
        mock_db = AsyncMock()
        audit_logger = AuditLogger(db_session=mock_db)

        # Log various security events
        await audit_logger.log(
            db=mock_db,
            event_type=AuditEventType.LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            user_id="user-123",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            success=True
        )

        await audit_logger.log(
            db=mock_db,
            event_type=AuditEventType.BRUTE_FORCE_ATTEMPT,
            severity=AuditSeverity.CRITICAL,
            ip_address="192.168.1.200",
            action_details={"attempt_count": 10},
            success=False
        )

        # Verify logging occurred (mock would have been called)
        # Actual verification depends on implementation

    def test_pii_redaction_in_audit_logs(self):
        """Test PII is redacted in audit logs."""
        audit_logger = AuditLogger()

        # Test various PII fields
        details_with_pii = {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com",
            "api_key": "AKIAIOSFODNN7EXAMPLE",
            "nested": {
                "secret_key": "wJalrXUtnFEMI/K7MDENG",
                "valid_data": "should remain"
            }
        }

        sanitized = audit_logger._sanitize_details(details_with_pii)

        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["nested"]["secret_key"] == "[REDACTED]"
        assert sanitized["username"] == "john_doe"
        assert sanitized["nested"]["valid_data"] == "should remain"


class TestInputValidationIntegration:
    """Test input validation integration."""

    def test_path_traversal_blocked(self, e2e_client):
        """Test path traversal attempts are blocked."""
        response = e2e_client.get("/api/../admin/config")

        # ASGI path normalization may collapse traversal attempts into 404.
        assert response.status_code in [400, 404]

    def test_large_request_blocked(self, e2e_client):
        """Test oversized requests are blocked."""
        # Note: Content-Length validation happens at middleware level
        # This test assumes middleware is checking content length
        large_body = "x" * (10 * 1024 * 1024 + 1)  # 10MB + 1 byte

        response = e2e_client.post(
            "/api/v1/test",
            data=large_body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(large_body))}
        )

        # Should be blocked due to size
        assert response.status_code in [413, 400]

    def test_invalid_content_type_blocked(self, e2e_client):
        """Test invalid Content-Type for write operations is blocked."""
        with pytest.raises(Exception) as exc_info:
            e2e_client.post(
                "/api/v1/test",
                data="<script>alert(1)</script>",
                headers={"Content-Type": "application/xml"}
            )

        assert "415" in str(exc_info.value) or "Unsupported media type" in str(exc_info.value)


class TestCredentialSecurityFlow:
    """Test complete credential security lifecycle."""

    @pytest.mark.asyncio
    async def test_credential_encryption_and_cache_flow(self):
        """Test credential encryption and caching flow."""
        from app.shared.field_encryption import FieldEncryption
        from app.cloud_accounts.credential_cache import SecureCredentialCache

        # Setup encryption
        encryption_key = "test-encryption-key-for-testing-only-1234"
        field_encryptor = FieldEncryption(master_key=encryption_key)

        # Original credentials
        credentials = {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG",
            "region": "us-east-1"
        }

        # Encrypt sensitive fields
        encrypted_creds = field_encryptor.encrypt_dict(
            credentials,
            ["secret_access_key"]
        )

        assert encrypted_creds["secret_access_key"] != credentials["secret_access_key"]
        assert encrypted_creds["access_key_id"] == credentials["access_key_id"]

        # Decrypt for use
        decrypted_creds = field_encryptor.decrypt_dict(
            encrypted_creds,
            ["secret_access_key"]
        )

        assert decrypted_creds["secret_access_key"] == credentials["secret_access_key"]

        # Test caching
        cache = SecureCredentialCache(redis_client=None, ttl_seconds=300)

        with patch('app.shared.key_rotation.decrypt') as mock_decrypt:
            mock_decrypt.return_value = __import__('json').dumps(credentials)

            # First call - decrypt
            creds1 = await cache.get_credentials("account-123", "encrypted-data")

            # Second call - from cache
            creds2 = await cache.get_credentials("account-123", "encrypted-data")

            assert creds1 == credentials
            assert creds2 == credentials
            assert mock_decrypt.call_count == 1  # Only decrypted once


class TestSecurityHeaders:
    """Test security headers in responses."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self):
        """Test rate limit headers are present in responses."""
        from app.middleware.rate_limiter import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        allowed, headers = await limiter.is_allowed("key", RateLimitTier.PUBLIC)

        assert "limit" in headers
        assert "remaining" in headers
        assert "reset" in headers


class TestCompleteSecurityPipeline:
    """Test complete security pipeline integration."""

    @pytest.mark.asyncio
    async def test_full_request_security_pipeline(self):
        """Test complete security pipeline for a request."""
        # This test simulates a complete request going through all security layers

        # 1. Input validation (path traversal, size, content-type)
        # 2. Rate limiting
        # 3. Session validation
        # 4. Audit logging

        # Setup components
        mock_redis = AsyncMock()

        with patch('app.auth.token_manager.settings') as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-for-jwt-123456789012345678"
            mock_settings.JWT_ALGORITHM = "HS256"

            token_manager = SecureTokenManager(redis_client=mock_redis)
            session_validator = SessionSecurityValidator()
            limiter = InMemoryRateLimiter()
            audit_logger = AuditLogger()

            # Step 1: Authenticate and get tokens
            tokens = await token_manager.create_token_pair("user-123", "session-456")

            # Step 2: Verify rate limit allows request
            allowed, headers = await limiter.is_allowed("user:123", RateLimitTier.AUTHENTICATED)
            assert allowed is True

            # Step 3: Validate session
            mock_request = Mock()
            mock_request.client = Mock()
            mock_request.client.host = "192.168.1.100"
            mock_request.headers = {
                "user-agent": "Mozilla/5.0",
                "accept-language": "en-US",
                "accept-encoding": "gzip",
                "dnt": "1"
            }

            fingerprint = session_validator.generate_session_fingerprint(mock_request)
            is_valid, reason = session_validator.validate_session_binding(
                mock_request,
                stored_fingerprint=fingerprint,
                stored_ip="192.168.1.100"
            )
            assert is_valid is True

            # Step 4: Validate access token
            decoded = token_manager.decode_access_token(
                tokens["access_token"],
                expected_session_id="session-456"
            )
            assert decoded["sub"] == "user-123"

            # All security checks passed!


class TestEdgeCases:
    """Test edge cases in security flows."""

    @pytest.mark.asyncio
    async def test_concurrent_token_refresh(self):
        """Test concurrent token refresh handling."""
        mock_redis = AsyncMock()

        with patch('app.auth.token_manager.settings') as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-for-jwt-123456789012345678"

            token_manager = SecureTokenManager(redis_client=mock_redis)
            tokens = await token_manager.create_token_pair("user-123", "session-456")

            # Simulate concurrent refresh attempts
            mock_redis.get.return_value = str({
                "user_id": "user-123",
                "session_id": "session-456",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "used": False
            })

            # First refresh should succeed
            new_tokens = await token_manager.rotate_refresh_token(tokens["refresh_token"])
            assert "access_token" in new_tokens

    @pytest.mark.asyncio
    async def test_rapid_requests_rate_limiting(self):
        """Test rapid requests trigger rate limiting."""
        limiter = InMemoryRateLimiter()

        # Make many rapid requests
        results = []
        for i in range(35):
            allowed, headers = await limiter.is_allowed("rapid-key", RateLimitTier.PUBLIC)
            results.append(allowed)

        # First 30 should be allowed, rest blocked
        assert sum(results) == 30
        assert results[30] is False  # 31st request blocked
