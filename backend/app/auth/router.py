import logging
import secrets

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.auth.schemas import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.auth.service import (
    create_session_binding,
    register_user,
    authenticate_user,
    create_access_token,
    hash_password,
    verify_password,
    blacklist_token,
    revoke_session_binding,
    create_password_reset_token,
    reset_password as reset_user_password,
)
from app.auth.dependencies import get_current_user, get_current_token
from app.auth.models import User
from app.shared.exceptions import BadRequestError, UnauthorizedError, ForbiddenError, NotFoundError
from app.auth.rate_limit import auth_limiter
from app.shared.enums import RolePurpose

router = APIRouter()
logger = logging.getLogger(__name__)

_COOKIE_NAME = "access_token"
_SESSION_COOKIE_NAME = "session_id"


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP, respecting X-Forwarded-For header for proxies."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one (client IP)
        return forwarded_for.split(",")[0].strip()
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    return None


def _set_auth_cookie(response: Response, token: str, session_id: str, secure: bool) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=TokenResponse, dependencies=[Depends(auth_limiter)])
async def register(request: Request, data: UserRegister, response: Response, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data.email, data.display_name, data.password)
    session_id = secrets.token_urlsafe(32)
    await create_session_binding(
        db,
        user.id,
        session_id,
        request.headers.get("user-agent"),
        _get_client_ip(request),
        request.headers.get("x-browser-fingerprint"),
    )
    token = create_access_token(user.id, session_id)
    _set_auth_cookie(response, token, session_id, secure=_is_secure_request(request))
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_limiter)])
async def login(request: Request, data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.email, data.password)
    session_id = secrets.token_urlsafe(32)
    await create_session_binding(
        db,
        user.id,
        session_id,
        request.headers.get("user-agent"),
        _get_client_ip(request),
        request.headers.get("x-browser-fingerprint"),
    )
    token = create_access_token(user.id, session_id)
    _set_auth_cookie(response, token, session_id, secure=_is_secure_request(request))
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.display_name is not None:
        current_user.display_name = data.display_name
    if data.password is not None:
        if not data.current_password:
            raise BadRequestError("current_password is required when changing password")
        if not verify_password(data.current_password, current_user.hashed_password):
            raise UnauthorizedError("Current password is incorrect")
        current_user.hashed_password = hash_password(data.password)
    await db.flush()
    return UserResponse.model_validate(current_user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    token: str = Depends(get_current_token),
    current_user: User = Depends(get_current_user),
):
    await blacklist_token(token)
    session_id = request.cookies.get(_SESSION_COOKIE_NAME)
    if session_id:
        await revoke_session_binding(session_id)
    secure = _is_secure_request(request)
    response.delete_cookie(key=_COOKIE_NAME, httponly=True, samesite="strict", secure=secure)
    response.delete_cookie(key=_SESSION_COOKIE_NAME, httponly=True, samesite="strict", secure=secure)


@router.post("/admin/unlock-user")
async def unlock_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlock a locked user account. Requires admin role."""
    if current_user.role != RolePurpose.MANAGER:
        raise ForbiddenError("Admin access required")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()
    return {"message": "User unlocked"}


@router.post("/forgot-password", dependencies=[Depends(auth_limiter)])
async def forgot_password(data: ForgotPasswordRequest):
    """Request a password reset email. Always returns success to prevent email enumeration."""
    token = await create_password_reset_token(data.email)
    if token:
        from app.notifications.email_service import send_email, _wrap_html

        reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password/{token}"
        subject = "[CostPilot] Reset your password"
        body_content = f"""
        <h2>Password Reset Request</h2>
        <p>We received a request to reset your password.</p>
        <p>Click the button below to choose a new password. This link expires in 15 minutes.</p>
        <p><a href="{reset_url}" class="btn">Reset Password</a></p>
        <p style="margin-top:24px;color:#999;font-size:13px;">
          If you did not request a password reset, you can safely ignore this email.<br>
          Your password will not be changed.
        </p>
        """
        html_body = _wrap_html(subject, body_content)
        try:
            await send_email(data.email, subject, html_body)
        except Exception as exc:
            logger.warning("Failed to send password reset email to %s: %s", data.email, exc)
    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password", dependencies=[Depends(auth_limiter)])
async def reset_password(data: ResetPasswordRequest):
    """Reset password using a valid reset token."""
    user = await reset_user_password(data.token, data.password)
    return {"message": "Password has been reset successfully."}
