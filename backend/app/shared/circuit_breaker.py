"""Circuit breaker pattern for fault tolerance."""

import asyncio
import time
from enum import Enum
from typing import Callable, Optional, Any
from functools import wraps
import logging

from app.shared.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject fast
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """Circuit breaker for external service calls.
    
    Prevents cascade failures by stopping calls to failing services.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        expected_exceptions: tuple = (Exception,)
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold
        self.expected_exceptions = expected_exceptions

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""

        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    self.success_count = 0
                    logger.info(f"Circuit {self.name} entering half-open state")
                else:
                    raise CircuitBreakerOpenError(self.name, self._time_until_reset())

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, self._time_until_reset())
                self.half_open_calls += 1

        # Execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exceptions as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._reset()
                    logger.info(f"Circuit {self.name} closed (recovered)")
            else:
                self.failure_count = max(0, self.failure_count - 1)

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} opened (recovery failed)")
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} opened ({self.failure_count} failures)")

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _time_until_reset(self) -> float:
        """Calculate time until circuit can be tested again."""
        if self.last_failure_time is None:
            return 0
        remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
        return max(0, remaining)

    def _reset(self):
        """Reset circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time = None

    def get_status(self) -> dict:
        """Get current circuit status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
            "time_until_reset": self._time_until_reset()
        }


# Decorator for easy usage
def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exceptions: tuple = (Exception,)
):
    """Decorator to apply circuit breaker to a function."""
    breaker = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exceptions=expected_exceptions
    )

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        wrapper._circuit_breaker = breaker
        return wrapper
    return decorator


# Circuit breaker registry for monitoring
class CircuitBreakerRegistry:
    """Registry of all circuit breakers for monitoring."""

    _breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def register(cls, name: str, breaker: CircuitBreaker):
        cls._breakers[name] = breaker

    @classmethod
    def get_breaker(cls, name: str) -> Optional[CircuitBreaker]:
        return cls._breakers.get(name)

    @classmethod
    def get_status(cls) -> dict:
        return {
            name: breaker.get_status()
            for name, breaker in cls._breakers.items()
        }

    @classmethod
    def get_all_breakers(cls) -> dict[str, CircuitBreaker]:
        return cls._breakers.copy()


# Pre-configured circuit breakers for CSP adapters

aws_circuit_breaker = CircuitBreaker(
    name="aws-api",
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exceptions=(Exception,)
)

azure_circuit_breaker = CircuitBreaker(
    name="azure-api",
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exceptions=(Exception,)
)

gcp_circuit_breaker = CircuitBreaker(
    name="gcp-api",
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exceptions=(Exception,)
)

# Analytics connector circuit breakers (longer recovery for analytics platforms)

bigquery_circuit_breaker = CircuitBreaker(
    name="bigquery-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

redshift_circuit_breaker = CircuitBreaker(
    name="redshift-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

athena_circuit_breaker = CircuitBreaker(
    name="athena-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

synapse_circuit_breaker = CircuitBreaker(
    name="synapse-api",
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exceptions=(Exception,)
)

# Register circuit breakers
CircuitBreakerRegistry.register("aws-api", aws_circuit_breaker)
CircuitBreakerRegistry.register("azure-api", azure_circuit_breaker)
CircuitBreakerRegistry.register("gcp-api", gcp_circuit_breaker)
CircuitBreakerRegistry.register("bigquery-api", bigquery_circuit_breaker)
CircuitBreakerRegistry.register("redshift-api", redshift_circuit_breaker)
CircuitBreakerRegistry.register("athena-api", athena_circuit_breaker)
CircuitBreakerRegistry.register("synapse-api", synapse_circuit_breaker)
