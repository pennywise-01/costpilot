"""Comprehensive tests for session security validation.

This module tests all features of the SessionSecurityValidator:
- Session fingerprint generation
- IP binding validation with subnet matching
- Fingerprint binding validation with HMAC comparison
- Support for strict and lenient binding modes
"""

import pytest
import hashlib
import hmac
from unittest.mock import Mock, patch

from app.auth.session_security import (
    SessionSecurityValidator,
    SessionBindingMiddleware,
)


@pytest.fixture
def validator():
    """Create a session security validator."""
    with patch('app.auth.session_security.settings') as mock_settings:
        mock_settings.MAX_SESSION_AGE_HOURS = 24
        mock_settings.REQUIRE_IP_BINDING = True
        mock_settings.REQUIRE_FINGERPRINT_BINDING = True
        return SessionSecurityValidator()


@pytest.fixture
def mock_request():
    """Create a mock request."""
    request = Mock()
    request.client = Mock()
    request.client.host = "192.168.1.100"
    request.headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "accept-language": "en-US,en;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "dnt": "1",
    }
    return request


class TestFingerprintGeneration:
    """Test session fingerprint generation."""

    def test_fingerprint_includes_ip(self, validator, mock_request):
        """Test fingerprint includes IP address."""
        fingerprint1 = validator.generate_session_fingerprint(mock_request)

        # Change IP
        mock_request.client.host = "192.168.1.101"
        fingerprint2 = validator.generate_session_fingerprint(mock_request)

        assert fingerprint1 != fingerprint2

    def test_fingerprint_includes_user_agent(self, validator, mock_request):
        """Test fingerprint includes User-Agent."""
        fingerprint1 = validator.generate_session_fingerprint(mock_request)

        # Change User-Agent
        mock_request.headers["user-agent"] = "Different Browser"
        fingerprint2 = validator.generate_session_fingerprint(mock_request)

        assert fingerprint1 != fingerprint2

    def test_fingerprint_includes_accept_language(self, validator, mock_request):
        """Test fingerprint includes Accept-Language."""
        fingerprint1 = validator.generate_session_fingerprint(mock_request)

        # Change language
        mock_request.headers["accept-language"] = "fr-FR,fr;q=0.9"
        fingerprint2 = validator.generate_session_fingerprint(mock_request)

        assert fingerprint1 != fingerprint2

    def test_fingerprint_includes_accept_encoding(self, validator, mock_request):
        """Test fingerprint includes Accept-Encoding."""
        fingerprint1 = validator.generate_session_fingerprint(mock_request)

        # Change encoding
        mock_request.headers["accept-encoding"] = "identity"
        fingerprint2 = validator.generate_session_fingerprint(mock_request)

        assert fingerprint1 != fingerprint2

    def test_fingerprint_includes_dnt(self, validator, mock_request):
        """Test fingerprint includes DNT header."""
        fingerprint1 = validator.generate_session_fingerprint(mock_request)

        # Change DNT
        mock_request.headers["dnt"] = "0"
        fingerprint2 = validator.generate_session_fingerprint(mock_request)

        assert fingerprint1 != fingerprint2

    def test_fingerprint_consistent_for_same_request(self, validator, mock_request):
        """Test same request produces same fingerprint."""
        fingerprint1 = validator.generate_session_fingerprint(mock_request)
        fingerprint2 = validator.generate_session_fingerprint(mock_request)

        assert fingerprint1 == fingerprint2

    def test_fingerprint_is_sha256_hash(self, validator, mock_request):
        """Test fingerprint is a SHA256 hash."""
        fingerprint = validator.generate_session_fingerprint(mock_request)

        # Should be a 64-character hex string
        assert len(fingerprint) == 64
        assert all(c in '0123456789abcdef' for c in fingerprint)

    def test_fingerprint_with_missing_headers(self, validator):
        """Test fingerprint generation with missing headers."""
        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {}  # Empty headers

        fingerprint = validator.generate_session_fingerprint(request)

        # Should still generate a fingerprint
        assert len(fingerprint) == 64

    def test_fingerprint_with_no_client(self, validator):
        """Test fingerprint generation with no client."""
        request = Mock()
        request.client = None
        request.headers = {"user-agent": "Test"}

        fingerprint = validator.generate_session_fingerprint(request)

        # Should still generate a fingerprint
        assert len(fingerprint) == 64


class TestIPBindingValidation:
    """Test IP binding validation."""

    def test_same_ip_valid(self, validator, mock_request):
        """Test same IP is valid."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip="192.168.1.100"
        )

        assert is_valid is True
        assert reason is None

    def test_different_ip_same_subnet_valid_in_lenient_mode(self, validator, mock_request):
        """Test different IP in same /24 subnet is valid in lenient mode."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip="192.168.1.50",
            strict_mode=False
        )

        assert is_valid is True
        assert reason is None

    def test_different_ip_different_subnet_invalid(self, validator, mock_request):
        """Test different IP in different subnet is invalid."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip="192.168.2.100"
        )

        assert is_valid is False
        assert reason == "IP_ADDRESS_MISMATCH"

    def test_different_ip_same_subnet_invalid_in_strict_mode(self, validator, mock_request):
        """Test different IP in same subnet is invalid in strict mode."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip="192.168.1.50",
            strict_mode=True
        )

        assert is_valid is False
        assert reason == "IP_ADDRESS_MISMATCH"

    def test_no_stored_ip_skips_validation(self, validator, mock_request):
        """Test validation passes when no IP is stored."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip=None
        )

        assert is_valid is True
        assert reason is None

    def test_no_current_ip_skips_validation(self, validator, mock_request):
        """Test validation passes when no current IP."""
        mock_request.client = None

        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip="192.168.1.100"
        )

        assert is_valid is True
        assert reason is None

    def test_ipv6_ip_binding(self, validator):
        """Test IP binding with IPv6 addresses."""
        request = Mock()
        request.client = Mock()
        request.client.host = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        request.headers = {}

        is_valid, reason = validator.validate_session_binding(
            request,
            stored_fingerprint=None,
            stored_ip="2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        )

        assert is_valid is True

    def test_malformed_ip_handling(self, validator, mock_request):
        """Test handling of malformed IP addresses."""
        # Should not crash with malformed IPs
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip="not-an-ip"
        )

        # Should fall back to exact comparison
        assert is_valid is False


class TestFingerprintBindingValidation:
    """Test fingerprint binding validation."""

    def test_same_fingerprint_valid(self, validator, mock_request):
        """Test same fingerprint is valid."""
        stored_fingerprint = validator.generate_session_fingerprint(mock_request)

        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=stored_fingerprint,
            stored_ip=None
        )

        assert is_valid is True
        assert reason is None

    def test_different_fingerprint_invalid(self, validator, mock_request):
        """Test different fingerprint is invalid."""
        stored_fingerprint = validator.generate_session_fingerprint(mock_request)

        # Change request to get different fingerprint
        mock_request.headers["user-agent"] = "Different Browser"
        current_fingerprint = validator.generate_session_fingerprint(mock_request)

        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=stored_fingerprint,
            stored_ip=None
        )

        assert is_valid is False
        assert reason == "FINGERPRINT_MISMATCH"

    def test_no_stored_fingerprint_skips_validation(self, validator, mock_request):
        """Test validation passes when no fingerprint is stored."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint=None,
            stored_ip=None
        )

        assert is_valid is True
        assert reason is None

    def test_hmac_comparison_timing_safe(self, validator, mock_request):
        """Test fingerprint comparison uses timing-safe HMAC."""
        stored_fingerprint = validator.generate_session_fingerprint(mock_request)

        # Mock hmac.compare_digest to verify it's called
        with patch('app.auth.session_security.hmac.compare_digest') as mock_compare:
            mock_compare.return_value = True

            validator.validate_session_binding(
                mock_request,
                stored_fingerprint=stored_fingerprint,
                stored_ip=None
            )

            mock_compare.assert_called_once()


class TestBindingConfiguration:
    """Test binding configuration options."""

    def test_both_bindings_disabled_allows_all(self, mock_request):
        """Test when both bindings are disabled, all requests are valid."""
        with patch('app.auth.session_security.settings') as mock_settings:
            mock_settings.REQUIRE_IP_BINDING = False
            mock_settings.REQUIRE_FINGERPRINT_BINDING = False
            validator = SessionSecurityValidator()

            is_valid, reason = validator.validate_session_binding(
                mock_request,
                stored_fingerprint="different-fingerprint",
                stored_ip="different-ip"
            )

            assert is_valid is True
            assert reason is None

    def test_only_ip_binding_enabled(self, mock_request):
        """Test when only IP binding is enabled."""
        with patch('app.auth.session_security.settings') as mock_settings:
            mock_settings.REQUIRE_IP_BINDING = True
            mock_settings.REQUIRE_FINGERPRINT_BINDING = False
            validator = SessionSecurityValidator()

            # Different fingerprint should be OK
            is_valid, reason = validator.validate_session_binding(
                mock_request,
                stored_fingerprint="different",
                stored_ip="192.168.1.100"
            )

            assert is_valid is True

    def test_only_fingerprint_binding_enabled(self, mock_request):
        """Test when only fingerprint binding is enabled."""
        with patch('app.auth.session_security.settings') as mock_settings:
            mock_settings.REQUIRE_IP_BINDING = False
            mock_settings.REQUIRE_FINGERPRINT_BINDING = True
            validator = SessionSecurityValidator()

            fingerprint = validator.generate_session_fingerprint(mock_request)

            # Different IP should be OK
            is_valid, reason = validator.validate_session_binding(
                mock_request,
                stored_fingerprint=fingerprint,
                stored_ip="10.0.0.1"
            )

            assert is_valid is True


class TestSubnetMatching:
    """Test subnet matching for IP binding."""

    def test_same_subnet_ipv4(self, validator):
        """Test IPs in same /24 subnet match."""
        result = validator._ips_in_same_subnet("192.168.1.100", "192.168.1.50")
        assert result is True

    def test_different_subnet_ipv4(self, validator):
        """Test IPs in different subnets don't match."""
        result = validator._ips_in_same_subnet("192.168.1.100", "192.168.2.100")
        assert result is False

    def test_same_ip(self, validator):
        """Test same IP matches."""
        result = validator._ips_in_same_subnet("10.0.0.1", "10.0.0.1")
        assert result is True

    def test_malformed_ip_fallback(self, validator):
        """Test malformed IPs fall back to exact comparison."""
        result = validator._ips_in_same_subnet("invalid", "also-invalid")
        assert result is False

    def test_partial_malformed_ip(self, validator):
        """Test partially malformed IPs."""
        result = validator._ips_in_same_subnet("192.168.1", "192.168.1.1")
        assert result is False  # Falls back to exact comparison

    def test_empty_ip(self, validator):
        """Test empty IPs."""
        result = validator._ips_in_same_subnet("", "")
        assert result is True  # Empty equals empty


class TestSessionBindingMiddleware:
    """Test SessionBindingMiddleware."""

    @pytest.mark.asyncio
    async def test_middleware_validates_session(self, mock_request):
        """Test middleware validates session binding."""
        middleware = SessionBindingMiddleware()

        # Create a stored session matching the request
        fingerprint = middleware.validator.generate_session_fingerprint(mock_request)

        session_data = {
            "fingerprint": fingerprint,
            "ip_address": "192.168.1.100"
        }

        result = await middleware.validate_request(mock_request, session_data)

        assert result is True

    @pytest.mark.asyncio
    async def test_middleware_rejects_invalid_session(self, mock_request):
        """Test middleware rejects invalid session."""
        middleware = SessionBindingMiddleware()

        session_data = {
            "fingerprint": "different-fingerprint",
            "ip_address": "10.0.0.1"
        }

        result = await middleware.validate_request(mock_request, session_data)

        assert result is False

    @pytest.mark.asyncio
    async def test_middleware_handles_strict_mode(self, mock_request):
        """Test middleware respects strict mode from session."""
        middleware = SessionBindingMiddleware()

        session_data = {
            "fingerprint": None,
            "ip_address": "192.168.1.100",
            "strict_mode": True
        }

        # Same IP should pass even in strict mode
        result = await middleware.validate_request(mock_request, session_data)
        assert result is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_fingerprint_with_unicode_headers(self, validator):
        """Test fingerprint with unicode header values."""
        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {
            "user-agent": "Browser/1.0 (日本語)",
            "accept-language": "中文",
        }

        fingerprint = validator.generate_session_fingerprint(request)

        # Should handle unicode without error
        assert len(fingerprint) == 64

    def test_very_long_header_values(self, validator):
        """Test fingerprint with very long header values."""
        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {
            "user-agent": "A" * 10000,
        }

        fingerprint = validator.generate_session_fingerprint(request)

        # Should handle long values without error
        assert len(fingerprint) == 64

    def test_both_bindings_invalid(self, validator, mock_request):
        """Test when both IP and fingerprint are invalid."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint="invalid-fingerprint",
            stored_ip="10.0.0.1"
        )

        # Should report IP mismatch first (order of validation)
        assert is_valid is False
        assert reason == "IP_ADDRESS_MISMATCH"

    def test_fingerprint_only_invalid_with_no_ip(self, validator, mock_request):
        """Test fingerprint mismatch when no IP stored."""
        is_valid, reason = validator.validate_session_binding(
            mock_request,
            stored_fingerprint="invalid-fingerprint",
            stored_ip=None
        )

        assert is_valid is False
        assert reason == "FINGERPRINT_MISMATCH"
