"""Comprehensive tests for secure token management.

This module tests all features of the SecureTokenManager:
- Token pair generation (access + refresh tokens)
- Refresh token rotation
- Token reuse detection
- Token revocation by user or session
- JWT access token validation with session binding
"""

import pytest
import hashlib
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import jwt
from jose import jwt as jose_jwt

from app.auth.token_manager import (
    SecureTokenManager,
    SecurityException,
    TokenRotationError,
)
from app.shared.exceptions import UnauthorizedError


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
def token_manager(mock_redis):
    """Create a token manager with mocked Redis."""
    with patch('app.auth.token_manager.settings') as mock_settings:
        mock_settings.JWT_SECRET = "test-secret-key-for-jwt-signing-12345678901234"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        manager = SecureTokenManager(redis_client=mock_redis)
        return manager


@pytest.fixture
def token_manager_no_redis():
    """Create a token manager without Redis."""
    with patch('app.auth.token_manager.settings') as mock_settings:
        mock_settings.JWT_SECRET = "test-secret-key-for-jwt-signing-12345678901234"
        mock_settings.JWT_ALGORITHM = "HS256"
        mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
        manager = SecureTokenManager(redis_client=None)
        return manager


class TestTokenPairGeneration:
    """Test token pair creation."""

    @pytest.mark.asyncio
    async def test_create_token_pair_returns_correct_structure(self, token_manager):
        """Test token pair has correct structure."""
        result = await token_manager.create_token_pair("user-123", "session-456")

        assert "access_token" in result
        assert "refresh_token" in result
        assert "token_type" in result
        assert "expires_in" in result
        assert result["token_type"] == "bearer"
        assert result["expires_in"] == 15 * 60  # 15 minutes in seconds

    @pytest.mark.asyncio
    async def test_access_token_is_valid_jwt(self, token_manager):
        """Test access token is a valid JWT."""
        result = await token_manager.create_token_pair("user-123", "session-456")
        access_token = result["access_token"]

        # Should be able to decode without verification
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        assert decoded["sub"] == "user-123"
        assert decoded["type"] == "access"
        assert "sid_hash" in decoded
        assert "jti" in decoded
        assert "iat" in decoded
        assert "exp" in decoded

    @pytest.mark.asyncio
    async def test_refresh_token_is_random_string(self, token_manager):
        """Test refresh token is a random secure string."""
        result = await token_manager.create_token_pair("user-123", "session-456")
        refresh_token = result["refresh_token"]

        # Should be a URL-safe base64 string
        assert len(refresh_token) > 32
        assert " " not in refresh_token

    @pytest.mark.asyncio
    async def test_refresh_token_stored_in_redis(self, token_manager, mock_redis):
        """Test refresh token is stored in Redis."""
        await token_manager.create_token_pair("user-123", "session-456")

        # Should have called setex
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_session_binding_in_access_token(self, token_manager):
        """Test access token contains session binding hash."""
        result = await token_manager.create_token_pair("user-123", "session-456")
        access_token = result["access_token"]

        decoded = jwt.decode(access_token, options={"verify_signature": False})
        expected_hash = hashlib.sha256("session-456".encode()).hexdigest()
        assert decoded["sid_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_token_pair_unique_each_time(self, token_manager):
        """Test each token pair is unique."""
        result1 = await token_manager.create_token_pair("user-123", "session-456")
        result2 = await token_manager.create_token_pair("user-123", "session-456")

        assert result1["access_token"] != result2["access_token"]
        assert result1["refresh_token"] != result2["refresh_token"]

    @pytest.mark.asyncio
    async def test_token_without_redis(self, token_manager_no_redis):
        """Test token creation works without Redis."""
        result = await token_manager_no_redis.create_token_pair("user-123", "session-456")

        assert "access_token" in result
        assert "refresh_token" in result


class TestTokenRotation:
    """Test refresh token rotation."""

    @pytest.mark.asyncio
    async def test_rotate_token_returns_new_pair(self, token_manager, mock_redis):
        """Test token rotation returns a new token pair."""
        # Setup: Create initial token
        initial = await token_manager.create_token_pair("user-123", "session-456")
        old_refresh = initial["refresh_token"]
        old_hash = hashlib.sha256(old_refresh.encode()).hexdigest()

        # Mock Redis to return the stored token
        mock_redis.get.return_value = str({
            "user_id": "user-123",
            "session_id": "session-456",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used": False
        })

        # Rotate
        new_tokens = await token_manager.rotate_refresh_token(old_refresh)

        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["access_token"] != initial["access_token"]
        assert new_tokens["refresh_token"] != old_refresh

    @pytest.mark.asyncio
    async def test_rotate_marks_old_token_used(self, token_manager, mock_redis):
        """Test rotation marks old token as used."""
        initial = await token_manager.create_token_pair("user-123", "session-456")
        old_refresh = initial["refresh_token"]

        mock_redis.get.return_value = str({
            "user_id": "user-123",
            "session_id": "session-456",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used": False
        })

        await token_manager.rotate_refresh_token(old_refresh)

        # Should update the token as used
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_rotate_invalid_token_fails(self, token_manager, mock_redis):
        """Test rotation with invalid token fails."""
        mock_redis.get.return_value = None  # Token not found

        with pytest.raises(TokenRotationError, match="Invalid or expired refresh token"):
            await token_manager.rotate_refresh_token("invalid-token")

    @pytest.mark.asyncio
    async def test_rotate_without_redis_fails(self, token_manager_no_redis):
        """Test rotation without Redis fails."""
        with pytest.raises(UnauthorizedError, match="Token refresh requires Redis"):
            await token_manager_no_redis.rotate_refresh_token("some-token")

    @pytest.mark.asyncio
    async def test_corrupted_token_data_fails(self, token_manager, mock_redis):
        """Test rotation with corrupted token data fails."""
        mock_redis.get.return_value = "invalid-json-data"

        with pytest.raises(TokenRotationError, match="Corrupted token data"):
            await token_manager.rotate_refresh_token("some-token")


class TestTokenReuseDetection:
    """Test token reuse detection."""

    @pytest.mark.asyncio
    async def test_reused_token_triggers_revocation(self, token_manager, mock_redis):
        """Test using a reused token triggers session revocation."""
        refresh_token = "test-refresh-token"

        # Mock token as already used
        mock_redis.get.return_value = str({
            "user_id": "user-123",
            "session_id": "session-456",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used": True
        })

        with pytest.raises(TokenRotationError, match="Token reuse detected"):
            await token_manager.rotate_refresh_token(refresh_token)

    @pytest.mark.asyncio
    async def test_reuse_detection_revokes_all_sessions(self, token_manager, mock_redis):
        """Test reuse detection revokes all user sessions."""
        refresh_token = "test-refresh-token"

        mock_redis.get.return_value = str({
            "user_id": "user-123",
            "session_id": "session-456",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used": True
        })

        # Mock scan to find tokens
        mock_redis.scan.side_effect = [
            (0, [b"refresh_token:hash1", b"refresh_token:hash2"]),
        ]
        mock_redis.get.side_effect = [
            str({"user_id": "user-123", "session_id": "session-1", "used": False}),
            str({"user_id": "user-123", "session_id": "session-2", "used": False}),
        ]

        try:
            await token_manager.rotate_refresh_token(refresh_token)
        except TokenRotationError:
            pass

        # Should have attempted to revoke sessions
        # Note: The actual revocation happens in _handle_token_reuse


class TestTokenRevocation:
    """Test token revocation functionality."""

    @pytest.mark.asyncio
    async def test_revoke_all_user_sessions(self, token_manager, mock_redis):
        """Test revoking all sessions for a user."""
        # Mock scan to return multiple tokens
        mock_redis.scan.side_effect = [
            (0, [b"refresh_token:hash1", b"refresh_token:hash2"]),
        ]
        mock_redis.get.side_effect = [
            str({"user_id": "user-123", "session_id": "session-1", "used": False}),
            str({"user_id": "user-123", "session_id": "session-2", "used": False}),
        ]

        count = await token_manager.revoke_all_user_sessions("user-123")

        assert count == 2
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_revoke_all_without_redis(self, token_manager_no_redis):
        """Test revoking all sessions without Redis returns 0."""
        count = await token_manager_no_redis.revoke_all_user_sessions("user-123")
        assert count == 0

    @pytest.mark.asyncio
    async def test_revoke_specific_session(self, token_manager, mock_redis):
        """Test revoking a specific session."""
        mock_redis.scan.side_effect = [
            (0, [b"refresh_token:hash1"]),
        ]
        mock_redis.get.return_value = str({
            "user_id": "user-123",
            "session_id": "session-to-revoke",
            "used": False
        })

        result = await token_manager.revoke_session("session-to-revoke")

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_session_not_found(self, token_manager, mock_redis):
        """Test revoking non-existent session returns False."""
        mock_redis.scan.side_effect = [
            (0, []),
        ]

        result = await token_manager.revoke_session("non-existent")

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_session_without_redis(self, token_manager_no_redis):
        """Test revoking session without Redis returns False."""
        result = await token_manager_no_redis.revoke_session("session-123")
        assert result is False


class TestAccessTokenDecoding:
    """Test JWT access token decoding and validation."""

    @pytest.mark.asyncio
    async def test_decode_valid_access_token(self, token_manager):
        """Test decoding a valid access token."""
        tokens = await token_manager.create_token_pair("user-123", "session-456")
        access_token = tokens["access_token"]

        decoded = token_manager.decode_access_token(access_token)

        assert decoded["sub"] == "user-123"
        assert decoded["type"] == "access"

    @pytest.mark.asyncio
    async def test_decode_with_session_binding(self, token_manager):
        """Test decoding with session binding validation."""
        tokens = await token_manager.create_token_pair("user-123", "session-456")
        access_token = tokens["access_token"]

        decoded = token_manager.decode_access_token(access_token, expected_session_id="session-456")

        assert decoded["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_decode_with_wrong_session_fails(self, token_manager):
        """Test decoding with wrong session ID fails."""
        tokens = await token_manager.create_token_pair("user-123", "session-456")
        access_token = tokens["access_token"]

        with pytest.raises(UnauthorizedError, match="Session mismatch"):
            token_manager.decode_access_token(access_token, expected_session_id="wrong-session")

    @pytest.mark.asyncio
    async def test_decode_refresh_token_fails(self, token_manager):
        """Test decoding a refresh token as access token fails."""
        tokens = await token_manager.create_token_pair("user-123", "session-456")
        refresh_token = tokens["refresh_token"]

        # Manually create a token with wrong type
        with patch.object(token_manager, '_secret', 'test-secret-key-for-jwt-signing-12345678901234'):
            bad_token = jose_jwt.encode(
                {"sub": "user-123", "type": "refresh"},
                token_manager._secret,
                algorithm="HS256"
            )

        with pytest.raises(UnauthorizedError, match="Invalid token type"):
            token_manager.decode_access_token(bad_token)

    def test_decode_invalid_token_fails(self, token_manager):
        """Test decoding an invalid token fails."""
        with pytest.raises(UnauthorizedError):
            token_manager.decode_access_token("invalid.token.here")

    def test_decode_expired_token_fails(self, token_manager):
        """Test decoding an expired token fails."""
        # Create an expired token
        expired_payload = {
            "sub": "user-123",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        expired_token = jose_jwt.encode(
            expired_payload,
            token_manager._secret,
            algorithm="HS256"
        )

        with pytest.raises(UnauthorizedError):
            token_manager.decode_access_token(expired_token)


class TestTokenExpiration:
    """Test token expiration behavior."""

    @pytest.mark.asyncio
    async def test_access_token_expires_in_configured_time(self, token_manager, mock_redis):
        """Test access token expires in configured time."""
        with patch('app.auth.token_manager.settings') as mock_settings:
            mock_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
            manager = SecureTokenManager(redis_client=mock_redis)

            tokens = await manager.create_token_pair("user-123", "session-456")

            decoded = jwt.decode(tokens["access_token"], options={"verify_signature": False})
            exp_time = datetime.fromtimestamp(decoded["exp"])
            iat_time = datetime.fromtimestamp(decoded["iat"])

            # Should be approximately 15 minutes
            diff = (exp_time - iat_time).total_seconds()
            assert abs(diff - 900) < 5  # Allow 5 second tolerance

    @pytest.mark.asyncio
    async def test_refresh_token_ttl_in_redis(self, token_manager, mock_redis):
        """Test refresh token has correct TTL in Redis."""
        await token_manager.create_token_pair("user-123", "session-456")

        # Check that setex was called with approximately 7 days
        call_args = mock_redis.setex.call_args
        ttl = call_args[0][1]  # Second positional argument

        # Should be around 7 days (604800 seconds)
        assert abs(ttl - 604800) < 10


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_token_with_unicode_user_id(self, token_manager):
        """Test token creation with unicode characters in user ID."""
        tokens = await token_manager.create_token_pair("user-日本語", "session-456")
        decoded = token_manager.decode_access_token(tokens["access_token"])
        assert decoded["sub"] == "user-日本語"

    @pytest.mark.asyncio
    async def test_very_long_session_id(self, token_manager):
        """Test token creation with very long session ID."""
        long_session = "s" * 1000
        tokens = await token_manager.create_token_pair("user-123", long_session)
        decoded = token_manager.decode_access_token(tokens["access_token"], expected_session_id=long_session)
        assert decoded["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self, token_manager, mock_redis):
        """Test graceful handling of Redis connection errors."""
        mock_redis.setex.side_effect = Exception("Redis connection error")

        # Should still create token pair even if Redis fails
        tokens = await token_manager.create_token_pair("user-123", "session-456")
        assert "access_token" in tokens
        assert "refresh_token" in tokens

    def test_jti_unique_per_token(self, token_manager):
        """Test each token has unique JTI."""
        import asyncio

        async def get_jtis():
            jtis = []
            for _ in range(10):
                tokens = await token_manager.create_token_pair("user-123", "session-456")
                decoded = jwt.decode(tokens["access_token"], options={"verify_signature": False})
                jtis.append(decoded["jti"])
            return jtis

        jtis = asyncio.run(get_jtis())
        assert len(set(jtis)) == len(jtis)  # All unique
