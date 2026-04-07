from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import secrets

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.config import settings
from app.auth.models import User, SessionBinding, SessionRevokeReason
from app.shared.exceptions import ConflictError, UnauthorizedError, NotFoundError
from app.shared.utils.time import utc_now

_redis_client: aioredis.Redis | None = None
_SESSION_KEY_PREFIX = "session_binding:"
MAX_CONCURRENT_SESSIONS = 5


async def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def blacklist_token(token: str) -> None:
    """Add a JWT to the blacklist until it expires."""
    r = await _get_redis()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        exp = payload.get("exp", 0)
        ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 0)
        if ttl > 0:
            await r.setex(f"token_blacklist:{token}", ttl, "1")
    except JWTError:
        pass


async def is_token_blacklisted(token: str) -> bool:
    r = await _get_redis()
    return await r.exists(f"token_blacklist:{token}") > 0


def _session_storage_key(session_id: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{session_id}"


def _user_agent_binding_hash(user_agent: str | None) -> str:
    normalized = (user_agent or "").strip()
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _ip_binding_hash(client_ip: str | None) -> str:
    normalized = (client_ip or "").strip()
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _fingerprint_binding_hash(fingerprint: str | None) -> str:
    """Hash browser fingerprint for session binding.
    
    This helps prevent session replay attacks even when IP addresses
    are the same (e.g., localhost testing or same network).
    """
    normalized = (fingerprint or "").strip()
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def create_session_binding(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    user_agent: str | None,
    client_ip: str | None = None,
    fingerprint: str | None = None,
) -> None:
    """Persist server-side session metadata for replay detection."""
    # Check existing sessions
    result = await db.execute(
        select(SessionBinding).where(
            SessionBinding.user_id == user_id,
            SessionBinding.expires_at > datetime.now(timezone.utc),
            SessionBinding.revoked_at.is_(None),
        )
    )
    active_sessions = result.scalars().all()

    if len(active_sessions) >= MAX_CONCURRENT_SESSIONS:
        # Evict oldest
        oldest = sorted(active_sessions, key=lambda s: s.created_at)[0]
        oldest.revoked_at = datetime.now(timezone.utc)
        oldest.revoke_reason = SessionRevokeReason.MAX_CONCURRENT_SESSIONS
        await db.flush()

    r = await _get_redis()
    key = _session_storage_key(session_id)
    ttl_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    await r.hset(
        key,
        mapping={
            "user_id": user_id,
            "ua_hash": _user_agent_binding_hash(user_agent),
            "ip_hash": _ip_binding_hash(client_ip),
            "fp_hash": _fingerprint_binding_hash(fingerprint),
        },
    )
    await r.expire(key, ttl_seconds)

    # Create DB record for session tracking
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    db_session = SessionBinding(
        user_id=user_id,
        session_id=session_id,
        expires_at=expires_at,
    )
    db.add(db_session)
    await db.flush()


async def is_session_binding_valid(
    user_id: str,
    session_id: str,
    user_agent: str | None,
    client_ip: str | None = None,
    fingerprint: str | None = None,
) -> bool:
    """Validate server-side session metadata against request context."""
    r = await _get_redis()
    key = _session_storage_key(session_id)
    binding = await r.hgetall(key)
    if not binding:
        return False

    bound_user_id = binding.get("user_id", "")
    if not secrets.compare_digest(bound_user_id, user_id):
        return False

    bound_ua_hash = binding.get("ua_hash", "")
    expected_ua_hash = _user_agent_binding_hash(user_agent)
    if not bound_ua_hash or not secrets.compare_digest(bound_ua_hash, expected_ua_hash):
        return False

    bound_ip_hash = binding.get("ip_hash", "")
    expected_ip_hash = _ip_binding_hash(client_ip)
    if not bound_ip_hash or not secrets.compare_digest(bound_ip_hash, expected_ip_hash):
        return False

    # Validate browser fingerprint if present
    # This helps prevent replay attacks when IP is the same (e.g., localhost)
    bound_fp_hash = binding.get("fp_hash", "")
    if bound_fp_hash:
        expected_fp_hash = _fingerprint_binding_hash(fingerprint)
        if not secrets.compare_digest(bound_fp_hash, expected_fp_hash):
            return False

    return True


async def revoke_session_binding(session_id: str) -> None:
    """Delete server-side session metadata."""
    r = await _get_redis()
    await r.delete(_session_storage_key(session_id))


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${hashed}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, stored_hash = hashed.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000).hex()
        return secrets.compare_digest(computed, stored_hash)
    except (ValueError, AttributeError):
        return False


def _session_binding_hash(session_id: str) -> str:
    """Derive a server-keyed digest used to bind JWTs to session cookie values."""
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        session_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_access_token(user_id: str, session_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "sid": _session_binding_hash(session_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str, expected_session_id: str | None = None) -> str:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        session_id_hash: str = payload.get("sid")
        if user_id is None or session_id_hash is None:
            raise UnauthorizedError("Invalid token")
        if expected_session_id is not None:
            expected_hash = _session_binding_hash(expected_session_id)
            if not secrets.compare_digest(session_id_hash, expected_hash):
                raise UnauthorizedError("Invalid session")
        return user_id
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")


async def register_user(
    db: AsyncSession, email: str, display_name: str, password: str
) -> User:
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    if result.scalar_one_or_none():
        raise ConflictError("User with this email already exists")

    user = User(
        email=email,
        display_name=display_name,
        hashed_password=hash_password(password),
        verified=False,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("Invalid email or password")

    # Check if account is locked
    if user.locked_until is not None and user.locked_until > utc_now():
        remaining = user.locked_until - utc_now()
        minutes = int(remaining.total_seconds() / 60) + 1
        raise UnauthorizedError(f"Account is locked. Try again in {minutes} minutes")

    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = utc_now() + timedelta(minutes=15)
        await db.flush()
        raise UnauthorizedError("Invalid email or password")

    # Successful login — reset lockout counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = utc_now()
    await db.flush()
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    return user


async def close_redis_client() -> None:
    """Close Redis client and release connections."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logging.info("Redis client closed")
