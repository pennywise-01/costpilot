"""Comprehensive tests for dependency injection framework.

This module tests all features of the dependency injection system:
- Protocol definitions
- ServiceContainer for dependency management
- InjectableService base class
- Mock providers for testing
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from contextlib import asynccontextmanager

from app.shared.dependencies import (
    ServiceContainer,
    InjectableService,
    MockCacheProvider,
    MockConfigProvider,
    MockLoggerProvider,
    create_test_container,
)


class TestMockCacheProvider:
    """Test MockCacheProvider."""

    def test_initialization_empty(self):
        """Test initialization with no data."""
        cache = MockCacheProvider()
        assert cache._data == {}

    def test_initialization_with_data(self):
        """Test initialization with initial data."""
        cache = MockCacheProvider(initial_data={"key": "value"})
        assert cache._data["key"] == "value"

    @pytest.mark.asyncio
    async def test_get_existing_key(self):
        """Test get returns value for existing key."""
        cache = MockCacheProvider(initial_data={"key": "value"})
        result = await cache.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_get_missing_key(self):
        """Test get returns None for missing key."""
        cache = MockCacheProvider()
        result = await cache.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_value(self):
        """Test set stores value."""
        cache = MockCacheProvider()
        await cache.set("key", "value")
        assert cache._data["key"] == "value"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Test set with TTL stores value."""
        cache = MockCacheProvider()
        await cache.set("key", "value", ttl=300)
        assert cache._data["key"] == "value"
        assert cache._ttl["key"] == 300

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        """Test delete removes existing key."""
        cache = MockCacheProvider(initial_data={"key": "value"})
        await cache.delete("key")
        assert "key" not in cache._data

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        """Test delete nonexistent key doesn't error."""
        cache = MockCacheProvider()
        await cache.delete("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test exists returns True for existing key."""
        cache = MockCacheProvider(initial_data={"key": "value"})
        result = await cache.exists("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test exists returns False for missing key."""
        cache = MockCacheProvider()
        result = await cache.exists("missing")
        assert result is False


class TestMockConfigProvider:
    """Test MockConfigProvider."""

    def test_initialization(self):
        """Test initialization."""
        config = MockConfigProvider()
        assert config._config == {}

    def test_get_existing(self):
        """Test get returns existing value."""
        config = MockConfigProvider()
        config._config["key"] = "value"
        result = config.get("key")
        assert result == "value"

    def test_get_missing_with_default(self):
        """Test get returns default for missing key."""
        config = MockConfigProvider()
        result = config.get("missing", "default")
        assert result == "default"

    def test_get_int(self):
        """Test get_int returns integer."""
        config = MockConfigProvider()
        config._config["number"] = "42"
        result = config.get_int("number")
        assert result == 42

    def test_get_int_missing(self):
        """Test get_int returns default for missing."""
        config = MockConfigProvider()
        result = config.get_int("missing", default=10)
        assert result == 10

    def test_get_bool_true(self):
        """Test get_bool returns True."""
        config = MockConfigProvider()
        config._config["flag"] = True
        result = config.get_bool("flag")
        assert result is True

    def test_get_bool_false(self):
        """Test get_bool returns False."""
        config = MockConfigProvider()
        config._config["flag"] = False
        result = config.get_bool("flag")
        assert result is False

    def test_get_bool_missing(self):
        """Test get_bool returns default for missing."""
        config = MockConfigProvider()
        result = config.get_bool("missing", default=True)
        assert result is True


class TestMockLoggerProvider:
    """Test MockLoggerProvider."""

    def test_initialization(self):
        """Test initialization."""
        logger = MockLoggerProvider()
        assert logger.messages == []

    def test_debug_log(self):
        """Test debug logging."""
        logger = MockLoggerProvider()
        logger.debug("Debug message", extra={"key": "value"})

        assert len(logger.messages) == 1
        assert logger.messages[0]["level"] == "debug"
        assert logger.messages[0]["message"] == "Debug message"

    def test_info_log(self):
        """Test info logging."""
        logger = MockLoggerProvider()
        logger.info("Info message")

        assert len(logger.messages) == 1
        assert logger.messages[0]["level"] == "info"

    def test_warning_log(self):
        """Test warning logging."""
        logger = MockLoggerProvider()
        logger.warning("Warning message")

        assert len(logger.messages) == 1
        assert logger.messages[0]["level"] == "warning"

    def test_error_log(self):
        """Test error logging."""
        logger = MockLoggerProvider()
        logger.error("Error message", exc_info=True)

        assert len(logger.messages) == 1
        assert logger.messages[0]["level"] == "error"
        assert logger.messages[0]["kwargs"]["exc_info"] is True

    def test_multiple_logs(self):
        """Test multiple log messages."""
        logger = MockLoggerProvider()
        logger.debug("Debug")
        logger.info("Info")
        logger.warning("Warning")

        assert len(logger.messages) == 3


class TestServiceContainer:
    """Test ServiceContainer."""

    def test_initialization(self):
        """Test initialization."""
        container = ServiceContainer()
        assert container.db is None
        assert container.cache is None
        assert container.config is None
        assert container.logger is None

    def test_initialization_with_providers(self):
        """Test initialization with providers."""
        cache = MockCacheProvider()
        config = MockConfigProvider()
        logger = MockLoggerProvider()

        container = ServiceContainer(
            cache_provider=cache,
            config_provider=config,
            logger_provider=logger
        )

        assert container.cache is cache
        assert container.config is config
        assert container.logger is logger

    @pytest.mark.asyncio
    async def test_with_cache_hit(self):
        """Test with_cache returns cached value."""
        cache = MockCacheProvider(initial_data={"key": "cached-value"})
        container = ServiceContainer(cache_provider=cache)

        async def fetch_func():
            return "fresh-value"

        result = await container.with_cache("key", fetch_func)

        assert result == "cached-value"

    @pytest.mark.asyncio
    async def test_with_cache_miss(self):
        """Test with_cache fetches and caches on miss."""
        cache = MockCacheProvider()
        container = ServiceContainer(cache_provider=cache)

        async def fetch_func():
            return "fresh-value"

        result = await container.with_cache("key", fetch_func)

        assert result == "fresh-value"
        assert cache._data["key"] == "fresh-value"

    @pytest.mark.asyncio
    async def test_with_cache_no_cache_provider(self):
        """Test with_cache without cache provider."""
        container = ServiceContainer()

        async def fetch_func():
            return "value"

        result = await container.with_cache("key", fetch_func)

        assert result == "value"

    @pytest.mark.asyncio
    async def test_session_raises_without_db(self):
        """Test session raises without database provider."""
        container = ServiceContainer()

        with pytest.raises(RuntimeError, match="Database provider not configured"):
            async with container.session():
                pass


class TestInjectableService:
    """Test InjectableService."""

    def test_initialization(self):
        """Test initialization with container."""
        container = ServiceContainer()
        service = InjectableService(container)

        assert service.container is container

    @pytest.mark.asyncio
    async def test_with_cache_delegates_to_container(self):
        """Test with_cache delegates to container."""
        cache = MockCacheProvider(initial_data={"key": "value"})
        container = ServiceContainer(cache_provider=cache)
        service = InjectableService(container)

        async def fetch():
            return "fresh"

        result = await service.with_cache("key", fetch)

        assert result == "value"

    def test_log_delegates_to_container(self):
        """Test log delegates to container logger."""
        logger = MockLoggerProvider()
        container = ServiceContainer(logger_provider=logger)
        service = InjectableService(container)

        service.log("info", "Test message")

        assert len(logger.messages) == 1
        assert logger.messages[0]["message"] == "Test message"

    def test_log_no_logger_configured(self):
        """Test log without logger doesn't error."""
        container = ServiceContainer()
        service = InjectableService(container)

        service.log("info", "Test message")  # Should not raise


class TestCreateTestContainer:
    """Test create_test_container factory."""

    def test_creates_container_with_mock_providers(self):
        """Test factory creates container with mock providers."""
        container = create_test_container()

        assert isinstance(container.cache, MockCacheProvider)
        assert isinstance(container.config, MockConfigProvider)
        assert isinstance(container.logger, MockLoggerProvider)

    def test_configurable_cache_data(self):
        """Test factory accepts cache data."""
        container = create_test_container(cache_data={"key": "value"})

        assert container.cache._data["key"] == "value"

    def test_configurable_config_values(self):
        """Test factory accepts config values."""
        container = create_test_container(config={"setting": "value"})

        assert container.config._config["setting"] == "value"


class TestIntegration:
    """Integration tests for DI system."""

    @pytest.mark.asyncio
    async def test_full_service_with_dependencies(self):
        """Test full service using all dependencies."""
        container = create_test_container(
            cache_data={"user-1": {"name": "John"}},
            config={"max_users": 100}
        )

        class UserService(InjectableService):
            async def get_user(self, user_id):
                return await self.with_cache(
                    f"user-{user_id}",
                    self._fetch_user
                )

            async def _fetch_user(self):
                return {"name": "Default"}

            def check_limit(self):
                max_users = self.container.config.get_int("max_users")
                self.log("info", f"Max users: {max_users}")
                return max_users

        service = UserService(container)

        user = await service.get_user(1)
        assert user["name"] == "John"

        limit = service.check_limit()
        assert limit == 100

        assert len(container.logger.messages) == 1

    @pytest.mark.asyncio
    async def test_caching_behavior(self):
        """Test complete caching behavior."""
        container = create_test_container()

        call_count = 0

        async def expensive_operation():
            nonlocal call_count
            call_count += 1
            return {"data": f"result-{call_count}"}

        # First call - should execute
        result1 = await container.with_cache("key", expensive_operation)
        assert call_count == 1
        assert result1["data"] == "result-1"

        # Second call - should use cache
        result2 = await container.with_cache("key", expensive_operation)
        assert call_count == 1  # Not incremented
        assert result2["data"] == "result-1"


class TestEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_cache_none_value(self):
        """Test caching None value."""
        cache = MockCacheProvider()
        container = ServiceContainer(cache_provider=cache)

        async def fetch():
            return None

        result = await container.with_cache("key", fetch)

        assert result is None
        assert cache._data["key"] is None

    def test_config_get_various_types(self):
        """Test config get with various types."""
        config = MockConfigProvider()
        config._config = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "list": [1, 2, 3],
        }

        assert config.get("string") == "value"
        assert config.get("number") == 42
        assert config.get("float") == 3.14
        assert config.get("bool") is True
        assert config.get("list") == [1, 2, 3]

    def test_logger_with_exception(self):
        """Test logger with exception info."""
        logger = MockLoggerProvider()

        try:
            raise ValueError("Test error")
        except ValueError:
            logger.error("Error occurred", exc_info=True)

        assert logger.messages[0]["kwargs"]["exc_info"] is True

    @pytest.mark.asyncio
    async def test_service_container_with_real_async(self):
        """Test service container with real async operations."""
        container = create_test_container()

        async def async_fetch():
            await __import__('asyncio').sleep(0.01)
            return "async-result"

        result = await container.with_cache("key", async_fetch)
        assert result == "async-result"
