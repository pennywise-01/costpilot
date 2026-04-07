from fastapi import HTTPException, status
from typing import Optional, Any
import uuid


# Base exception classes

class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BadRequestError(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class TooManyRequestsError(HTTPException):
    def __init__(self, detail: str = "Too many requests", retry_after_seconds: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after_seconds)},
        )


# New structured exception hierarchy for reliability

class AppException(Exception):
    """Base application exception with error tracking."""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: Optional[dict] = None,
        retryable: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable
        self.error_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "error_id": self.error_id,
                "retryable": self.retryable,
                **self.details
            }
        }


class CloudProviderException(AppException):
    """Exception for cloud provider API failures."""

    def __init__(
        self,
        provider: str,
        message: str,
        error_code: str = "CLOUD_PROVIDER_ERROR",
        retryable: bool = True,
        **kwargs
    ):
        self.provider = provider
        super().__init__(
            message=f"{provider}: {message}",
            error_code=error_code,
            status_code=502,
            retryable=retryable,
            details={"provider": provider, **kwargs}
        )


class CacheException(AppException):
    """Exception for cache-related failures."""

    def __init__(self, message: str, fallback_available: bool = True):
        super().__init__(
            message=message,
            error_code="CACHE_ERROR",
            status_code=503 if not fallback_available else 200,
            retryable=True,
            details={"fallback_available": fallback_available}
        )


class DatabaseException(AppException):
    """Exception for database failures."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=503,
            retryable=retryable
        )


class ValidationException(AppException):
    """Exception for validation failures."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            retryable=False,
            details={"field": field} if field else {}
        )


class RateLimitException(AppException):
    """Exception for rate limit violations."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            retryable=True,
            details={"retry_after": retry_after}
        )


class CircuitBreakerOpenError(AppException):
    """Exception raised when circuit breaker is open."""

    def __init__(self, circuit_name: str, retry_after: float):
        super().__init__(
            message=f"Service temporarily unavailable. Circuit {circuit_name} is open.",
            error_code="CIRCUIT_OPEN",
            status_code=503,
            retryable=True,
            details={
                "circuit_name": circuit_name,
                "retry_after": retry_after
            }
        )


class RetryExhaustedError(AppException):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, message: str, attempts: int, last_error: str):
        super().__init__(
            message=message,
            error_code="RETRY_EXHAUSTED",
            status_code=503,
            retryable=False,
            details={
                "attempts": attempts,
                "last_error": last_error
            }
        )


class DegradationError(AppException):
    """Exception for graceful degradation failures."""

    def __init__(self, message: str, primary_error: str, fallback_error: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="DEGRADATION_FAILED",
            status_code=503,
            retryable=False,
            details={
                "primary_error": primary_error,
                "fallback_error": fallback_error
            }
        )
