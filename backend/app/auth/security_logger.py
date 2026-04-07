"""Security event logging module for authentication and session management."""
import hashlib
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import SecurityEvent, SecurityEventType


def _hash_ip_address(ip_address: str | None) -> str | None:
    """Hash IP address for privacy before storing."""
    if not ip_address:
        return None
    return hashlib.sha256(ip_address.encode()).hexdigest()


async def log_security_event(
    db: AsyncSession,
    event_type: SecurityEventType,
    user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session_id: str | None = None,
    details: str | None = None,
    success: bool = False,
) -> SecurityEvent:
    """Log a security event to the database.
    
    Args:
        db: Database session
        event_type: Type of security event
        user_id: User ID associated with the event (if applicable)
        ip_address: Client IP address (will be hashed before storage)
        user_agent: Client user agent string
        session_id: Session ID (if applicable)
        details: Additional details about the event
        success: Whether the security check passed or failed
    
    Returns:
        The created SecurityEvent instance
    """
    event = SecurityEvent(
        user_id=user_id,
        event_type=event_type,
        ip_address_hash=_hash_ip_address(ip_address),
        user_agent=user_agent,
        session_id=session_id,
        details=details,
        success=success,
    )
    db.add(event)
    await db.flush()
    return event


async def log_session_validation_failure(
    db: AsyncSession,
    user_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
    reason: str,
) -> SecurityEvent:
    """Log a session validation failure."""
    return await log_security_event(
        db=db,
        event_type=SecurityEventType.SESSION_VALIDATION_FAILED,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=f"Session validation failed: {reason}",
        success=False,
    )


async def log_session_binding_mismatch(
    db: AsyncSession,
    user_id: str,
    session_id: str,
    ip_address: str | None,
    user_agent: str | None,
    mismatch_type: str,
) -> SecurityEvent:
    """Log a session binding mismatch (potential session replay attack)."""
    return await log_security_event(
        db=db,
        event_type=SecurityEventType.SESSION_BINDING_MISMATCH,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
        details=f"Session binding mismatch detected: {mismatch_type}. Possible session replay attack.",
        success=False,
    )


async def log_suspicious_ip_change(
    db: AsyncSession,
    user_id: str,
    old_ip_hash: str | None,
    new_ip_hash: str | None,
    user_agent: str | None,
) -> SecurityEvent:
    """Log a suspicious IP address change."""
    return await log_security_event(
        db=db,
        event_type=SecurityEventType.SUSPICIOUS_IP_CHANGE,
        user_id=user_id,
        user_agent=user_agent,
        details=f"IP address change detected. Old hash: {old_ip_hash[:16] if old_ip_hash else 'none'}..., New hash: {new_ip_hash[:16] if new_ip_hash else 'none'}...",
        success=False,
    )


async def log_token_blacklisted(
    db: AsyncSession,
    user_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> SecurityEvent:
    """Log an attempt to use a blacklisted token."""
    return await log_security_event(
        db=db,
        event_type=SecurityEventType.TOKEN_BLACKLISTED,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details="Attempt to use a blacklisted/revoked token",
        success=False,
    )
