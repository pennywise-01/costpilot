"""Secure token management with rotation and revocation."""

import secrets
import hashlib
import logging
from datetime import timedelta
from typing import Optional, Any
import redis.asyncio as redis
from jose import jwt, JWTError

from app.config import settings
from app.shared.exceptions import UnauthorizedError
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)


class SecurityException(Exception):
    """Security-related exception."""
    pass


class TokenRotationError(SecurityException):
    """Raised when token rotation detects reuse (potential theft)."""
    pass


class SecureTokenManager:
    """Manage secure token lifecycle with rotation and revocation."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        access_minutes = getattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 15)
        try:
            access_minutes = int(access_minutes)
        except (TypeError, ValueError):
            access_minutes = 15
        if access_minutes <= 0:
            access_minutes = 15

        self._access_token_ttl = access_minutes * 60  # Convert to seconds
        self._refresh_token_ttl = 7 * 24 * 60 * 60  # 7 days

        algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
        self._algorithm = algorithm if isinstance(algorithm, str) and algorithm else "HS256"

        secret = getattr(settings, "JWT_SECRET", None)
        if not isinstance(secret, str) or not secret:
            secret = "development-secret-change-in-production"
        self._secret = secret

    async def create_token_pair(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Create access and refresh token pair."""
        access_token = self._generate_access_token(user_id, session_id)
        refresh_token = self._generate_refresh_token()

        # Store refresh token hash for revocation capability
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await self._store_refresh_token(token_hash, user_id, session_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self._access_token_ttl
        }

    def _generate_access_token(self, user_id: str, session_id: str) -> str:
        """Generate JWT access token."""
        session_id_hash = hashlib.sha256(session_id.encode()).hexdigest()
        payload = {
            "sub": user_id,
            "sid_hash": session_id_hash,
            "type": "access",
            "iat": utc_now(),
            "exp": utc_now() + timedelta(seconds=self._access_token_ttl),
            "jti": secrets.token_urlsafe(16)  # Unique token ID
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def _generate_refresh_token(self) -> str:
        """Generate cryptographically secure refresh token."""
        return secrets.token_urlsafe(32)

    async def _store_refresh_token(self, token_hash: str, user_id: str, session_id: str):
        """Store refresh token metadata in Redis."""
        if not self.redis:
            return

        key = f"refresh_token:{token_hash}"
        value = {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": utc_now().isoformat(),
            "used": False
        }
        try:
            await self.redis.setex(key, self._refresh_token_ttl, str(value))
        except Exception as exc:
            # Token issuance should remain available even when Redis is degraded.
            logger.warning(f"Failed to persist refresh token metadata: {exc}")

    async def rotate_refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Rotate refresh token on use (detect reuse = potential theft)."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        key = f"refresh_token:{token_hash}"

        if not self.redis:
            # Without Redis, we can't track rotation - just create new pair
            raise UnauthorizedError("Token refresh requires Redis")

        # Check if token exists
        stored = await self.redis.get(key)
        if not stored:
            # Token doesn't exist - already used or invalid
            raise TokenRotationError("Invalid or expired refresh token")

        # Parse stored data
        import ast
        try:
            stored_data = ast.literal_eval(stored.decode() if isinstance(stored, bytes) else stored)
        except (ValueError, SyntaxError) as exc:
            logger.warning("Corrupted token data for key %s: %s", key, exc)
            raise TokenRotationError("Corrupted token data")

        # Check if token was already used
        if stored_data.get("used", False):
            # Token reuse detected - potential theft!
            await self._handle_token_reuse(stored_data["user_id"], stored_data["session_id"])
            raise TokenRotationError("Token reuse detected. All sessions revoked.")

        # Mark token as used
        stored_data["used"] = True
        await self.redis.setex(key, 60, str(stored_data))  # Keep for 1 minute for duplicate detection

        # Create new token pair
        new_pair = await self.create_token_pair(
            stored_data["user_id"],
            stored_data["session_id"]
        )

        return new_pair

    async def _handle_token_reuse(self, user_id: str, session_id: str):
        """Handle detected token reuse - revoke all sessions for user."""
        # Revoke all sessions for this user
        await self.revoke_all_user_sessions(user_id)

        # Log security event
        # TODO: Integrate with audit logger
        pass

    async def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user (password change, suspicious activity)."""
        if not self.redis:
            return 0

        # Find all refresh tokens for this user
        pattern = "refresh_token:*"
        cursor = 0
        revoked = 0

        while True:
            scan_result = await self.redis.scan(cursor, match=pattern, count=100)
            if not isinstance(scan_result, (tuple, list)) or len(scan_result) != 2:
                break

            cursor, keys = scan_result
            for key in keys:
                stored = await self.redis.get(key)
                if stored:
                    try:
                        import ast
                        data = ast.literal_eval(stored.decode() if isinstance(stored, bytes) else stored)
                        if data.get("user_id") == user_id:
                            await self.redis.delete(key)
                            revoked += 1
                    except (ValueError, SyntaxError) as exc:
                        logger.warning("Failed to parse token data for key %s during revoke: %s", key, exc)

            if cursor == 0:
                break

        return revoked

    async def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session."""
        if not self.redis:
            return False

        # Find and delete refresh token for this session
        pattern = "refresh_token:*"
        cursor = 0

        while True:
            scan_result = await self.redis.scan(cursor, match=pattern, count=100)
            if not isinstance(scan_result, (tuple, list)) or len(scan_result) != 2:
                break

            cursor, keys = scan_result
            for key in keys:
                stored = await self.redis.get(key)
                if stored:
                    try:
                        import ast
                        data = ast.literal_eval(stored.decode() if isinstance(stored, bytes) else stored)
                        if data.get("session_id") == session_id:
                            await self.redis.delete(key)
                            return True
                    except (ValueError, SyntaxError) as exc:
                        logger.warning("Failed to parse token data for key %s during session revoke: %s", key, exc)

            if cursor == 0:
                break

        return False

    def decode_access_token(self, token: str, expected_session_id: str | None = None) -> dict[str, Any]:
        """Decode and validate access token."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])

            if payload.get("type") != "access":
                raise UnauthorizedError("Invalid token type")

            if expected_session_id:
                session_id_hash = hashlib.sha256(expected_session_id.encode()).hexdigest()
                if payload.get("sid_hash") != session_id_hash:
                    raise UnauthorizedError("Session mismatch")

            return payload

        except JWTError:
            raise UnauthorizedError("Invalid or expired token")
