"""Unified error handling for cloud providers.

This module provides standardized error mapping and handling for
AWS, Azure, and GCP API errors.
"""

import functools
import logging
from typing import TypeVar, Callable, Optional, Any

from app.shared.exceptions import (
    CloudProviderException,
    ValidationException,
    NotFoundError,
    BadRequestError
)

T = TypeVar('T')
logger = logging.getLogger(__name__)


class ProviderErrorMapper:
    """Maps provider-specific errors to standardized exceptions."""

    # AWS error code mappings
    AWS_ERRORS = {
        "AccessDeniedException": (
            "CLOUD_PERMISSION_DENIED",
            "Cloud provider permissions insufficient. Please check IAM policies."
        ),
        "InvalidParameterException": (
            "CLOUD_INVALID_PARAMETER",
            "Invalid parameter provided to cloud provider API."
        ),
        "ThrottlingException": (
            "CLOUD_RATE_LIMITED",
            "Cloud provider API rate limit exceeded. Please retry later."
        ),
        "ServiceUnavailableException": (
            "CLOUD_SERVICE_UNAVAILABLE",
            "Cloud provider service temporarily unavailable. Please retry later."
        ),
        "OptInRequired": (
            "CLOUD_OPT_IN_REQUIRED",
            "AWS service opt-in required. Please enable the service in AWS console."
        ),
        "EndpointConnectionError": (
            "CLOUD_CONNECTION_ERROR",
            "Unable to connect to cloud provider endpoint."
        ),
    }

    # Azure HTTP status code mappings
    AZURE_ERRORS = {
        400: ("CLOUD_BAD_REQUEST", "Invalid request to cloud provider API."),
        401: ("CLOUD_AUTH_FAILED", "Authentication failed. Please verify credentials."),
        403: ("CLOUD_ACCESS_DENIED", "Access denied. Please check role assignments."),
        404: ("CLOUD_RESOURCE_NOT_FOUND", "Resource not found in cloud provider."),
        429: ("CLOUD_RATE_LIMITED", "Rate limit exceeded. Please retry later."),
        500: ("CLOUD_SERVER_ERROR", "Cloud provider internal error."),
        503: ("CLOUD_SERVICE_UNAVAILABLE", "Cloud provider service temporarily unavailable."),
    }

    # GCP error reason mappings (from google.api_core.exceptions)
    GCP_ERRORS = {
        "PERMISSION_DENIED": ("CLOUD_PERMISSION_DENIED", "Access denied. Please check IAM permissions."),
        "UNAUTHENTICATED": ("CLOUD_AUTH_FAILED", "Authentication failed. Please verify credentials."),
        "RESOURCE_EXHAUSTED": ("CLOUD_RATE_LIMITED", "Rate limit or quota exceeded. Please retry later."),
        "UNAVAILABLE": ("CLOUD_SERVICE_UNAVAILABLE", "Service temporarily unavailable. Please retry later."),
        "NOT_FOUND": ("CLOUD_RESOURCE_NOT_FOUND", "Resource not found in cloud provider."),
        "INVALID_ARGUMENT": ("CLOUD_INVALID_PARAMETER", "Invalid parameter provided to cloud provider API."),
    }

    @classmethod
    def map_aws_error(cls, error_code: str, original_message: str) -> CloudProviderException:
        """Map AWS error to standardized exception.
        
        Args:
            error_code: AWS error code
            original_message: Original error message
            
        Returns:
            Standardized CloudProviderException
        """
        mapped = cls.AWS_ERRORS.get(error_code)
        if mapped:
            error_code, message = mapped
        else:
            error_code = "CLOUD_PROVIDER_ERROR"
            message = f"AWS API error: {original_message}"

        return CloudProviderException(
            provider="AWS",
            message=message,
            error_code=error_code,
            retryable=error_code in ["CLOUD_RATE_LIMITED", "CLOUD_SERVICE_UNAVAILABLE", "CLOUD_CONNECTION_ERROR"]
        )

    @classmethod
    def map_azure_error(cls, status_code: int, original_message: str) -> CloudProviderException:
        """Map Azure error to standardized exception.
        
        Args:
            status_code: HTTP status code
            original_message: Original error message
            
        Returns:
            Standardized CloudProviderException
        """
        mapped = cls.AZURE_ERRORS.get(status_code)
        if mapped:
            error_code, message = mapped
        else:
            error_code = "CLOUD_PROVIDER_ERROR"
            message = f"Azure API error ({status_code}): {original_message}"

        return CloudProviderException(
            provider="AZURE",
            message=message,
            error_code=error_code,
            retryable=status_code in [429, 500, 503]
        )

    @classmethod
    def map_gcp_error(cls, error_reason: str, original_message: str) -> CloudProviderException:
        """Map GCP error to standardized exception.
        
        Args:
            error_reason: GCP error reason code
            original_message: Original error message
            
        Returns:
            Standardized CloudProviderException
        """
        mapped = cls.GCP_ERRORS.get(error_reason)
        if mapped:
            error_code, message = mapped
        else:
            error_code = "CLOUD_PROVIDER_ERROR"
            message = f"GCP API error: {original_message}"

        return CloudProviderException(
            provider="GCP",
            message=message,
            error_code=error_code,
            retryable=error_reason in ["RESOURCE_EXHAUSTED", "UNAVAILABLE"]
        )


def handle_provider_errors(provider: str):
    """Decorator to standardize provider error handling.
    
    Automatically catches exceptions and converts them to standardized
    CloudProviderException instances.
    
    Usage:
        @handle_provider_errors("AWS")
        async def get_resources():
            # AWS API call that might fail
            pass
    
    Args:
        provider: Provider name (AWS, AZURE, GCP)
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except CloudProviderException:
                # Already standardized, re-raise
                raise
            except Exception as e:
                # Log original error for debugging
                logger.error(f"{provider} API error in {func.__name__}: {e}")

                # Map to standardized exception
                if provider == "AWS":
                    error_code = ""
                    if hasattr(e, 'response'):
                        error_response = e.response
                        if isinstance(error_response, dict):
                            error_code = error_response.get('Error', {}).get('Code', '')
                    raise ProviderErrorMapper.map_aws_error(error_code, str(e))
                elif provider == "AZURE":
                    status_code = getattr(e, 'status_code', 500)
                    raise ProviderErrorMapper.map_azure_error(status_code, str(e))
                elif provider == "GCP":
                    error_reason = getattr(e, 'code', lambda: None)()
                    if error_reason is None:
                        error_reason = getattr(e, 'reason', "UNKNOWN")
                    raise ProviderErrorMapper.map_gcp_error(str(error_reason), str(e))
                else:
                    raise CloudProviderException(
                        provider=provider,
                        message=str(e),
                        error_code="CLOUD_PROVIDER_ERROR",
                        retryable=True
                    )
        return wrapper
    return decorator


def validate_required_params(*required_params: str):
    """Decorator to validate required parameters are present and not empty.
    
    Usage:
        @validate_required_params("access_key_id", "secret_access_key")
        async def create_aws_client(config: dict):
            # Config is guaranteed to have required params
            pass
    
    Args:
        required_params: Names of required parameters
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Try to find config dict in args or kwargs
            config = kwargs.get('config')
            if config is None and len(args) > 1:
                # Assume second positional arg might be config
                potential_config = args[1]
                if isinstance(potential_config, dict):
                    config = potential_config

            if isinstance(config, dict):
                missing = [param for param in required_params if not config.get(param)]
                if missing:
                    raise ValidationException(
                        f"Missing required parameters: {', '.join(missing)}",
                        field=missing[0]
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


class ErrorAggregator:
    """Aggregate multiple errors into a single report.
    
    Useful for batch operations where partial failures are acceptable.
    """

    def __init__(self):
        self.errors: list[dict[str, Any]] = []
        self.success_count = 0
        self.failure_count = 0

    def add_success(self, identifier: str | None = None):
        """Record a successful operation."""
        self.success_count += 1

    def add_error(self, identifier: str, error: Exception, context: dict | None = None):
        """Record a failed operation."""
        self.failure_count += 1
        self.errors.append({
            "item_id": identifier,
            "error": str(error),
            "error_type": type(error).__name__,
            "details": context or {}
        })

    def add_failure(self, item_id: str, error: Exception, details: dict | None = None):
        """Backward-compatible alias for add_error used by older callers."""
        self.add_error(item_id, error, details)

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return self.failure_count > 0

    def get_report(self, include_errors: bool = False) -> dict[str, Any]:
        """Get operation report with optional error details."""
        total = self.success_count + self.failure_count
        success_rate = self.success_count / total if total > 0 else 0

        report = {
            "total": total,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(success_rate, 2),
        }

        if include_errors:
            report["errors"] = self.errors

        return report

    def get_summary(self) -> dict[str, Any]:
        """Backward-compatible summary including errors."""
        return self.get_report(include_errors=True)

    def raise_if_all_failed(self):
        """Raise exception if all operations failed."""
        if self.failure_count > 0 and self.success_count == 0:
            raise CloudProviderException(
                provider="UNKNOWN",
                message=f"All operations failed: {self.errors}",
                error_code="ALL_OPERATIONS_FAILED",
                retryable=False
            )
