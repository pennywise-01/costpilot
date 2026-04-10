"""Retry logic with exponential backoff."""

import asyncio
import random
import logging
from typing import Callable, Optional, TypeVar, Any
from functools import wraps
from datetime import timedelta

from app.shared.exceptions import RetryExhaustedError, CloudProviderException
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)
T = TypeVar('T')


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
        return isinstance(error, self.config.retryable_exceptions)

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

AWS_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, CloudProviderException),
    jitter=True
)

AZURE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,  # Increased from 4 to handle rate limits
    base_delay=3.0,  # Increased from 2.0 for rate limit scenarios
    max_delay=120.0,  # Increased from 60.0 to allow longer waits for 429
    retryable_exceptions=(ConnectionError, TimeoutError, CloudProviderException),
    jitter=True
)

GCP_RETRY_CONFIG = RetryConfig(
    max_attempts=4,
    base_delay=1.5,
    max_delay=45.0,
    retryable_exceptions=(ConnectionError, TimeoutError, CloudProviderException),
    jitter=True
)

# Analytics connector retry configurations (longer delays for query platforms)

BIGQUERY_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    retryable_exceptions=(ConnectionError, TimeoutError, CloudProviderException),
    jitter=True
)

REDSHIFT_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=3.0,
    max_delay=120.0,
    retryable_exceptions=(ConnectionError, TimeoutError, CloudProviderException),
    jitter=True
)

ATHENA_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=3.0,
    max_delay=120.0,
    retryable_exceptions=(ConnectionError, TimeoutError, CloudProviderException),
    jitter=True
)

SYNAPSE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=3.0,
    max_delay=120.0,
    retryable_exceptions=(ConnectionError, TimeoutError, CloudProviderException),
    jitter=True
)
