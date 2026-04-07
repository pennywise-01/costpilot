"""Dependency injection framework.

Provides protocols and containers for dependency injection
to improve testability and reduce coupling.
"""

from typing import Protocol, Callable, Any, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseProvider(Protocol):
    """Protocol for database providers."""

    async def get_session(self) -> AsyncSession:
        """Get a database session."""
        ...


class CacheProvider(Protocol):
    """Protocol for cache providers."""

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        ...

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache."""
        ...

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        ...


class ConfigProvider(Protocol):
    """Protocol for configuration providers."""

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        ...

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        ...

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        ...


class LoggerProvider(Protocol):
    """Protocol for logger providers."""

    def debug(self, message: str, **kwargs) -> None:
        ...

    def info(self, message: str, **kwargs) -> None:
        ...

    def warning(self, message: str, **kwargs) -> None:
        ...

    def error(self, message: str, **kwargs) -> None:
        ...


class ServiceContainer:
    """Container for service dependencies.

    Provides a centralized way to manage and access dependencies
    throughout the application.

    Usage:
        container = ServiceContainer(
            db_provider=DatabaseProvider(),
            cache_provider=CacheProvider(),
            config_provider=ConfigProvider()
        )
        service = MyService(container)
    """

    def __init__(
        self,
        db_provider: DatabaseProvider | None = None,
        cache_provider: CacheProvider | None = None,
        config_provider: ConfigProvider | None = None,
        logger_provider: LoggerProvider | None = None
    ):
        self.db = db_provider
        self.cache = cache_provider
        self.config = config_provider
        self.logger = logger_provider

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session context.

        Automatically handles commit/rollback.

        Usage:
            async with container.session() as session:
                # Use session
                pass
        """
        if not self.db:
            raise RuntimeError("Database provider not configured")

        session = await self.db.get_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def with_cache(
        self,
        cache_key: str,
        fetch_func: Callable,
        ttl: int = 300
    ) -> Any:
        """Fetch with caching support.

        Tries cache first, then fetches fresh data if not found.

        Args:
            cache_key: Cache key
            fetch_func: Function to fetch fresh data
            ttl: Cache TTL in seconds

        Returns:
            Cached or fresh data
        """
        if not self.cache:
            return await fetch_func()

        # Try cache first
        try:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            # Graceful degradation: continue with source-of-truth fetch.
            pass

        # Fetch fresh data
        data = await fetch_func()

        # Store in cache
        try:
            await self.cache.set(cache_key, data, ttl)
        except Exception:
            # Cache storage failures should not fail requests.
            pass

        return data


class InjectableService:
    """Base class for services with dependency injection.

    Provides convenient access to common dependencies.

    Usage:
        class MyService(InjectableService):
            async def get_data(self):
                return await self.with_cache("key", self._fetch_data)
    """

    def __init__(self, container: ServiceContainer):
        self.container = container

    async def with_cache(
        self,
        cache_key: str,
        fetch_func: Callable,
        ttl: int = 300
    ) -> Any:
        """Fetch with caching support."""
        return await self.container.with_cache(cache_key, fetch_func, ttl)

    @asynccontextmanager
    async def session(self):
        """Get database session context."""
        async with self.container.session() as session:
            yield session

    def log(self, level: str, message: str, **kwargs):
        """Log a message if logger is configured."""
        if self.container.logger:
            getattr(self.container.logger, level)(message, **kwargs)


# Mock providers for testing

class MockCacheProvider:
    """Mock cache provider for testing."""

    def __init__(self, initial_data: dict | None = None):
        self._data = initial_data or {}
        self._ttl = {}

    async def get(self, key: str) -> Any | None:
        return self._data.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._data[key] = value
        self._ttl[key] = ttl

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._ttl.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._data

    def clear(self):
        """Clear all cached data."""
        self._data.clear()
        self._ttl.clear()


class MockConfigProvider:
    """Mock config provider for testing."""

    def __init__(self, config: dict | None = None):
        self._config = config or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        value = self._config.get(key, default)
        return int(value) if value is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self._config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value) if value is not None else default

    def set(self, key: str, value: Any):
        """Set a configuration value."""
        self._config[key] = value


class MockLoggerProvider:
    """Mock logger provider for testing."""

    def __init__(self):
        self.messages = []

    def _log(self, level: str, message: str, **kwargs):
        self.messages.append({
            "level": level,
            "message": message,
            "kwargs": kwargs
        })

    def debug(self, message: str, **kwargs) -> None:
        self._log("debug", message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._log("info", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log("warning", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._log("error", message, **kwargs)

    def get_messages(self, level: str | None = None) -> list[dict]:
        """Get logged messages, optionally filtered by level."""
        if level:
            return [m for m in self.messages if m["level"] == level]
        return self.messages

    def clear(self):
        """Clear all logged messages."""
        self.messages.clear()


# Factory functions for creating containers

def create_test_container(
    db_provider: DatabaseProvider | None = None,
    cache_data: dict | None = None,
    config: dict | None = None
) -> ServiceContainer:
    """Create a service container configured for testing.

    Args:
        db_provider: Optional database provider
        cache_data: Optional initial cache data
        config: Optional configuration values

    Returns:
        ServiceContainer configured for testing
    """
    return ServiceContainer(
        db_provider=db_provider,
        cache_provider=MockCacheProvider(cache_data),
        config_provider=MockConfigProvider(config),
        logger_provider=MockLoggerProvider()
    )
