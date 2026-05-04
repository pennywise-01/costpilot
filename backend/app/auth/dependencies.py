import logging

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

logger = logging.getLogger(__name__)

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
    path = request.url.path
    has_token_cookie = bool(request.cookies.get("access_token"))
    has_session_cookie = bool(request.cookies.get("session_id"))
    logger.warning(
        f"[AUTH-DEBUG] {request.method} {path} | "
        f"token_cookie={has_token_cookie} session_cookie={has_session_cookie} | "
        f"xfwd={request.headers.get('x-forwarded-for','')} "
        f"realip={request.headers.get('x-real-ip','')} "
        f"client={request.client.host if request.client else 'None'} | "
        f"ua={request.headers.get('user-agent','')[:60]} | "
        f"fp={request.headers.get('x-browser-fingerprint','')}"
    )

    token = _extract_token(request)
    session_id = _extract_session_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    
    if await is_token_blacklisted(token):
        logger.warning(f"[AUTH-DEBUG] {path} => token blacklisted")
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
        logger.warning(
            f"[AUTH-DEBUG] {path} => session binding INVALID | "
            f"user_id={user_id} session_id={session_id[:12]}... "
            f"ip={client_ip} ua={str(user_agent)[:40]} fp={fingerprint}"
        )
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
    logger.info(f"[AUTH-DEBUG] {path} => authenticated as {user.email}")
    return user
