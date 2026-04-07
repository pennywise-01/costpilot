"""Global exception handler middleware for centralized error handling."""

import traceback
import logging
import uuid
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.shared.exceptions import AppException
from app.shared.logging_config import correlation_id
from app.config import settings

logger = logging.getLogger(__name__)


class GlobalExceptionHandler(BaseHTTPMiddleware):
    """Centralized exception handling with logging and metrics."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except AppException as e:
            return await self._handle_app_exception(request, e)
        except HTTPException as e:
            return await self._handle_http_exception(request, e)
        except Exception as e:
            return await self._handle_unexpected_exception(request, e)

    async def _handle_http_exception(
        self,
        request: Request,
        exc: HTTPException
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions (including rate limit errors)."""
        
        # Log structured error
        log_data = {
            "error_type": "HTTPException",
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        }

        if exc.status_code >= 500:
            logger.error(f"HTTP error: {exc.status_code}", extra=log_data)
        elif exc.status_code == 429:
            logger.warning(f"Rate limit exceeded: {request.url.path}", extra=log_data)
        elif exc.status_code >= 400:
            logger.warning(f"HTTP error: {exc.status_code}", extra=log_data)

        headers = dict(exc.headers) if exc.headers else {}
        
        # Build response content
        content = {
            "error": {
                "code": self._get_error_code(exc.status_code),
                "message": exc.detail,
                "correlation_id": correlation_id.get() or "",
            }
        }

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=headers
        )

    def _get_error_code(self, status_code: int) -> str:
        """Map HTTP status code to error code."""
        codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT",
        }
        return codes.get(status_code, "UNKNOWN_ERROR")

    async def _handle_app_exception(
        self,
        request: Request,
        exc: AppException
    ) -> JSONResponse:
        """Handle known application exceptions."""

        # Log structured error
        log_data = {
            "error_id": exc.error_id,
            "error_code": exc.error_code,
            "path": request.url.path,
            "method": request.method,
            "retryable": exc.retryable,
            "status_code": exc.status_code
        }

        if exc.status_code >= 500:
            logger.error(f"Application error: {exc.error_code}", extra=log_data)
        elif exc.status_code >= 400:
            logger.warning(f"Application error: {exc.error_code}", extra=log_data)
        else:
            logger.info(f"Application error: {exc.error_code}", extra=log_data)

        # Audit log for security-relevant errors
        if exc.status_code >= 400:
            await self._audit_log_error(request, exc)

        response_data = exc.to_dict()

        # Add correlation ID to response
        response_data["correlation_id"] = correlation_id.get() or ""

        # Add debugging info in development
        if settings.DEBUG:
            response_data["error"]["debug"] = {
                "traceback": traceback.format_exc()
            }

        headers = {}
        if exc.error_code == "RATE_LIMIT_EXCEEDED":
            headers["Retry-After"] = str(exc.details.get("retry_after", 60))
        elif exc.error_code == "CIRCUIT_OPEN":
            headers["Retry-After"] = str(int(exc.details.get("retry_after", 60)))

        return JSONResponse(
            status_code=exc.status_code,
            content=response_data,
            headers=headers
        )

    async def _handle_unexpected_exception(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""

        error_id = str(uuid.uuid4())[:8]

        # Log full stack trace
        logger.exception(
            f"Unexpected error: {error_id}",
            extra={
                "error_id": error_id,
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__
            }
        )

        # Audit log critical error
        await self._audit_log_error(request, exc, critical=True)

        response = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "error_id": error_id,
                "correlation_id": correlation_id.get() or "",
            }
        }

        if settings.DEBUG:
            response["error"]["debug"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc()
            }

        return JSONResponse(
            status_code=500,
            content=response
        )

    async def _audit_log_error(self, request: Request, exc: Exception, critical: bool = False):
        """Log errors to audit system."""
        try:
            from app.security.audit_logger import get_audit_logger, AuditEventType, AuditSeverity

            audit_logger = get_audit_logger()

            # Get request info
            user_id = getattr(request.state, "user_id", None)
            org_id = getattr(request.state, "org_id", None)
            ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            # Determine severity
            severity = AuditSeverity.CRITICAL if critical else AuditSeverity.HIGH

            # Log the error
            # Note: We don't have access to db session here, so we just log to Python logger
            logger.warning(
                f"Error audit event: {type(exc).__name__}",
                extra={
                    "user_id": user_id,
                    "org_id": org_id,
                    "ip": ip,
                    "critical": critical
                }
            )
        except Exception as e:
            logger.error(f"Failed to audit log error: {e}")
