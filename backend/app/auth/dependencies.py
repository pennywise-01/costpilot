from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.models import User
from app.auth.service import (
    decode_access_token,
    get_user_by_id,
    is_session_binding_valid,
    is_token_blacklisted,
)
from app.auth.security_logger import (
    log_session_validation_failure,
    log_session_binding_mismatch,
    log_token_blacklisted,
)
from app.shared.exceptions import UnauthorizedError

def _extract_token(
    request: Request,
) -> str:
    token = request.cookies.get("access_token")
    if token:
        return token
    raise UnauthorizedError("Not authenticated")


def _extract_session_id(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    if session_id:
        return session_id
    raise UnauthorizedError("Session is missing")


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP, respecting X-Forwarded-For header for proxies."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def get_current_token(
    request: Request,
) -> str:
    return _extract_token(request)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_token(request)
    session_id = _extract_session_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    
    if await is_token_blacklisted(token):
        # Log blacklisted token usage attempt
        try:
            user_id = decode_access_token(token, expected_session_id=None)
            await log_token_blacklisted(db, user_id, client_ip, user_agent)
        except Exception:
            # If we can't decode the token, log without user_id
            await log_token_blacklisted(db, None, client_ip, user_agent)
        raise UnauthorizedError("Token has been revoked")
    
    user_id = decode_access_token(token, expected_session_id=session_id)
    fingerprint = request.headers.get("x-browser-fingerprint")
    
    if not await is_session_binding_valid(
        user_id=user_id,
        session_id=session_id,
        user_agent=user_agent,
        client_ip=client_ip,
        fingerprint=fingerprint,
    ):
        # Log session binding mismatch (potential replay attack)
        await log_session_binding_mismatch(
            db=db,
            user_id=user_id,
            session_id=session_id,
            ip_address=client_ip,
            user_agent=user_agent,
            mismatch_type="IP, User-Agent, or Fingerprint mismatch",
        )
        raise UnauthorizedError("Session is invalid")

    user = await get_user_by_id(db, user_id)

    return user
