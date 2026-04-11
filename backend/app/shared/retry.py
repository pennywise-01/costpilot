"""Retry logic with exponential backoff."""

import asyncio
import random
import logging
from typing import Callable, Optional, TypeVar, Any
from functools import wraps
from datetime import timedelta

from app.shared.exceptions import RetryExhaustedError, CloudProviderException, RateLimitException
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)
T = TypeVar('T')


# Retryable HTTP status codes for CSP errors
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# AWS error codes that are transient/retryable
_RETRYABLE_AWS_CODES = {
    "ThrottlingException", "Throttling", "RequestLimitExceeded",
    "ServiceUnavailable", "InternalError", "SlowDown",
    "RequestTimeout", "PriorRequestNotComplete",
}


def is_retryable_csp_error(error: Exception) -> bool:
    """Determine if a CSP error is transient and worth retrying.
    
    Checks both exception type and error code/message to decide retryability.
    This handles cases where CSP SDKs raise generic exceptions with
    retryable error codes embedded in the error details.
    """
    # Always retry connection and timeout errors
    if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True
    
    # CloudProviderException: respect the retryable flag explicitly
    if isinstance(error, CloudProviderException):
        return error.retryable
    
    # Check for HTTP status code in error attributes
    status_code = getattr(error, "status_code", None) or getattr(error, "statusCode", None)
    if status_code and int(status_code) in _RETRYABLE_STATUS_CODES:
        return True
    
    # Check for response attribute with status code (boto3 ClientError)
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        http_status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if http_status and int(http_status) in _RETRYABLE_STATUS_CODES:
            return True
        # Check AWS error code
        error_code = response.get("Error", {}).get("Code", "")
        if error_code in _RETRYABLE_AWS_CODES:
            return True
    
    
    # Check error message for rate limit indicators
    error_str = str(error).lower()
    if any(indicator in error_str for indicator in ("429", "rate limit", "too many requests", "throttl")):
        return True
    
    return False


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,),
        on_retry: Optional[Callable] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self.on_retry = on_retry


class RetryContext:
    """Context for tracking retry attempts."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.attempt = 0
        self.start_time = utc_now()
        self.errors: list[Exception] = []

    def should_retry(self, error: Exception) -> bool:
        """Check if we should retry based on error type and attempts."""
        if self.attempt >= self.config.max_attempts:
            return False
        # First check explicit exception type list
        if isinstance(error, self.config.retryable_exceptions):
            return True
        # Then check CSP-specific retryability heuristics
        return is_retryable_csp_error(error)

    def calculate_delay(self) -> float:
        """Calculate delay before next retry with exponential backoff."""
        # Check if the last error was a rate limit (429)
        is_rate_limit = False
        if self.errors:
            last_error = str(self.errors[-1])
            is_rate_limit = "429" in last_error or "Too many requests" in last_error or "rate limit" in last_error.lower()
        
        if is_rate_limit:
            # Longer backoff for rate limits: 5s, 10s, 20s, 40s, 60s
            delay = 5.0 * (2.0 ** (self.attempt - 1))
            logger.warning(f"Rate limit error detected, using extended backoff")
        else:
            # Normal backoff: 1s, 2s, 4s, 8s, 16s
            delay = self.config.base_delay * (self.config.exponential_base ** (self.attempt - 1))
        
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            # Add random jitter (0-25% of delay)
            delay = delay * (0.75 + random.random() * 0.25)

        return delay

    def get_duration(self) -> timedelta:
        """Get total duration of retry attempts."""
        return utc_now() - self.start_time


async def with_retry(
    func: Callable[..., T],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> T:
    """Execute function with retry logic."""
    config = config or RetryConfig()
    context = RetryContext(config)

    while True:
        context.attempt += 1

        try:
            result = await func(*args, **kwargs)

            if context.attempt > 1:
                logger.info(
                    f"Function succeeded after {context.attempt} attempts",
                    extra={"duration_ms": context.get_duration().total_seconds() * 1000}
                )

            return result

        except Exception as e:
            context.errors.append(e)

            if not context.should_retry(e):
                logger.error(
                    f"Function failed after {context.attempt} attempts",
                    extra={"errors": [str(err) for err in context.errors]}
                )
                raise RetryExhaustedError(
                    message="All retry attempts exhausted",
                    attempts=context.attempt,
                    last_error=str(e)
                )

            delay = context.calculate_delay()

            logger.warning(
                f"Attempt {context.attempt} failed: {e}. Retrying in {delay:.2f}s",
                extra={"error": str(e), "next_delay": delay}
            )

            if config.on_retry:
                await config.on_retry(context.attempt, e, delay)

            await asyncio.sleep(delay)


# Decorator for easy usage
def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (Exception,),
    jitter: bool = True
):
    """Decorator to add retry logic to a function."""
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions,
        jitter=jitter
    )

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_retry(func, config, *args, **kwargs)
        return wrapper
    return decorator


# CSP-specific retry configurations
# Note: is_retryable_csp_error() provides additional heuristic-based retryability
# checking beyond these explicit exception types.

try:
    from botocore.exceptions import ClientError as BotoClientError
    _AWS_EXCEPTIONS = (ConnectionError, TimeoutError, CloudProviderException, RateLimitException, BotoClientError)
except ImportError:
    _AWS_EXCEPTIONS = (ConnectionError, TimeoutError, CloudProviderException, RateLimitException)

try:
    from azure.core.exceptions import HttpResponseError as AzureHttpResponseError
    _AZURE_EXCEPTIONS = (ConnectionError, TimeoutError, CloudProviderException, RateLimitException, AzureHttpResponseError)
except ImportError:
    _AZURE_EXCEPTIONS = (ConnectionError, TimeoutError, CloudProviderException, RateLimitException)

try:
    from google.api_core.exceptions import GoogleAPIError, ServiceUnavailable as GCPServiceUnavailable
    _GCP_EXCEPTIONS = (ConnectionError, TimeoutError, CloudProviderException, RateLimitException, GoogleAPIError)
except ImportError:
    _GCP_EXCEPTIONS = (ConnectionError, TimeoutError, CloudProviderException, RateLimitException)

AWS_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=_AWS_EXCEPTIONS,
    jitter=True
)

AZURE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=3.0,
    max_delay=120.0,
    retryable_exceptions=_AZURE_EXCEPTIONS,
    jitter=True
)

GCP_RETRY_CONFIG = RetryConfig(
    max_attempts=4,
    base_delay=1.5,
    max_delay=45.0,
    retryable_exceptions=_GCP_EXCEPTIONS,
    jitter=True
)

# Analytics connector retry configurations (longer delays for query platforms)

BIGQUERY_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    retryable_exceptions=_GCP_EXCEPTIONS,
    jitter=True
)

REDSHIFT_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=3.0,
    max_delay=120.0,
    retryable_exceptions=_AWS_EXCEPTIONS,
    jitter=True
)

ATHENA_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=3.0,
    max_delay=120.0,
    retryable_exceptions=_AWS_EXCEPTIONS,
    jitter=True
)

SYNAPSE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=3.0,
    max_delay=120.0,
    retryable_exceptions=_AZURE_EXCEPTIONS,
    jitter=True
)
