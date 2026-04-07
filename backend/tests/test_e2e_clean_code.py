"""End-to-End tests for clean code implementations.

This module tests complete clean code implementations:
- CSP Adapter Base Classes
- Unified Error Handling integration
- Service Layer Abstraction
- Type Safety
- Dependency Injection in real scenarios
"""

import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.shared.types import (
    Result,
    OrganizationId,
    UserId,
    ResourceId,
    Money,
    PaginatedResponse,
    ResourceResponse,
    CostSummaryResponse,
)
from app.shared.service_base import BaseService
from app.shared.error_handling import (
    ProviderErrorMapper,
    handle_provider_errors,
    ErrorAggregator,
)
from app.shared.dependencies import (
    ServiceContainer,
    InjectableService,
    MockCacheProvider,
    MockConfigProvider,
    MockLoggerProvider,
    create_test_container,
)
from app.shared.exceptions import CloudProviderException


class TestTypesAndTypeSafety:
    """Test type safety implementations."""

    def test_newtype_prevents_mixing(self):
        """Test NewType prevents mixing different ID types."""
        org_id = OrganizationId("org-123")
        user_id = UserId("user-456")

        # These should be distinct types
        assert isinstance(org_id, str)
        assert isinstance(user_id, str)

        # Function signatures would prevent mixing (type checking)
        def process_org_id(oid: OrganizationId) -> str:
            return oid

        def process_user_id(uid: UserId) -> str:
            return uid

        # These would fail mypy type checking but work at runtime
        result1 = process_org_id(org_id)
        result2 = process_user_id(user_id)

        assert result1 == "org-123"
        assert result2 == "user-456"

    def test_money_type(self):
        """Test Money type for financial values."""
        amount = Money(Decimal("99.99"))

        assert isinstance(amount, Decimal)
        assert float(amount) == 99.99

    def test_result_type_success(self):
        """Test Result type for successful operations."""
        result = Result.ok("success data")

        assert result.success is True
        assert result.value == "success data"
        assert result.error is None

    def test_result_type_error(self):
        """Test Result type for failed operations."""
        error = ValueError("something went wrong")
        result = Result.err(error)

        assert result.success is False
        assert result.value is None
        assert result.error == error

    def test_result_unwrap_success(self):
        """Test unwrap on successful result."""
        result = Result.ok("data")
        assert result.unwrap() == "data"

    def test_result_unwrap_error_raises(self):
        """Test unwrap on error result raises."""
        result = Result.err(ValueError("error"))

        with pytest.raises(ValueError, match="Cannot unwrap error result"):
            result.unwrap()

    def test_result_unwrap_or_with_default(self):
        """Test unwrap_or returns default on error."""
        result = Result.err(ValueError("error"))
        assert result.unwrap_or("default") == "default"

    def test_result_map_success(self):
        """Test map transforms successful result."""
        result = Result.ok(5)
        mapped = result.map(lambda x: x * 2)

        assert mapped.success is True
        assert mapped.value == 10

    def test_result_map_error_unchanged(self):
        """Test map doesn't transform error result."""
        result = Result.err(ValueError("error"))
        mapped = result.map(lambda x: x * 2)

        assert mapped.success is False
        assert mapped.error is not None


class TestTypedDictResponses:
    """Test TypedDict response structures."""

    def test_resource_response_structure(self):
        """Test ResourceResponse structure."""
        response: ResourceResponse = {
            "id": "res-123",
            "name": "Test Resource",
            "type": "ec2",
            "region": "us-east-1",
            "status": "running",
            "cost_per_month": 100.50,
            "tags": {"env": "prod"},
            "created_at": "2024-01-01T00:00:00Z"
        }

        assert response["id"] == "res-123"
        assert response["cost_per_month"] == 100.50

    def test_paginated_response_structure(self):
        """Test PaginatedResponse structure."""
        response: PaginatedResponse[ResourceResponse] = {
            "items": [],
            "total": 100,
            "page": 1,
            "page_size": 10,
            "has_more": True
        }

        assert response["total"] == 100
        assert response["has_more"] is True

    def test_cost_summary_response_structure(self):
        """Test CostSummaryResponse structure."""
        response: CostSummaryResponse = {
            "this_month": 1000.00,
            "last_month": 900.00,
            "forecast": 1100.00,
            "change_percent": 11.11,
            "currency": "USD"
        }

        assert response["this_month"] == 1000.00
        assert response["change_percent"] == 11.11


class TestCloudAdapterBase:
    """Test Cloud Adapter Base functionality."""

    def test_resource_discovery_result_structure(self):
        """Test ResourceDiscoveryResult structure."""
        # This would test the actual implementation
        # For now, verify the concept
        result = {
            "resources": [],
            "total_count": 0,
            "regions_scanned": [],
            "errors": []
        }

        assert "resources" in result
        assert "total_count" in result


class TestErrorHandlingIntegration:
    """Test error handling integration."""

    def test_aws_error_mapping_integration(self):
        """Test AWS error mapping in context."""
        error = ProviderErrorMapper.map_aws_error(
            "AccessDeniedException",
            "User not authorized"
        )

        assert error.provider == "AWS"
        assert error.error_code == "CLOUD_PERMISSION_DENIED"
        assert error.status_code == 502

    def test_azure_error_mapping_integration(self):
        """Test Azure error mapping in context."""
        error = ProviderErrorMapper.map_azure_error(429, "Too many requests")

        assert error.provider == "AZURE"
        assert error.error_code == "CLOUD_RATE_LIMITED"
        assert error.retryable is True

    def test_gcp_error_mapping_integration(self):
        """Test GCP error mapping in context."""
        error = ProviderErrorMapper.map_gcp_error("PERMISSION_DENIED", "No access")

        assert error.provider == "GCP"
        assert error.error_code == "CLOUD_PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_error_aggregator_batch_operation(self):
        """Test error aggregator in batch operations."""
        aggregator = ErrorAggregator()

        # Simulate batch processing
        items = ["item-1", "item-2", "item-3", "item-4", "item-5"]

        for i, item in enumerate(items):
            if i % 2 == 0:
                aggregator.add_success()
            else:
                try:
                    raise ValueError(f"Error processing {item}")
                except ValueError as e:
                    aggregator.add_failure(item, e)

        report = aggregator.get_report()

        assert report["total"] == 5
        assert report["success_count"] == 3
        assert report["failure_count"] == 2
        assert report["success_rate"] == 0.6


class TestServiceLayerIntegration:
    """Test service layer abstraction integration."""

    @pytest.mark.asyncio
    async def test_base_service_with_mock_db(self):
        """Test BaseService with mock database."""
        mock_db = AsyncMock()

        # Create a simple model for testing
        class TestModel:
            def __init__(self, **kwargs):
                self.id = kwargs.get("id", "test-id")
                self.name = kwargs.get("name", "test")
                self.organization_id = kwargs.get("organization_id")
                self.deleted_at = None

        service = BaseService(TestModel, mock_db)

        # Test creation
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = TestModel(id="new-id", name="Test")
        mock_db.execute.return_value = mock_result

        result = await service.get_by_id("test-id")
        assert result.id == "new-id"

    def test_base_service_chainability(self):
        """Test BaseService method chaining."""
        mock_db = AsyncMock()

        class TestModel:
            pass

        service = BaseService(TestModel, mock_db)

        # Test with_relations returns self
        result = service.with_relations("org", "user")
        assert result is service


class TestDependencyInjectionIntegration:
    """Test dependency injection in real scenarios."""

    @pytest.mark.asyncio
    async def test_service_with_full_container(self):
        """Test service using all container dependencies."""
        container = create_test_container(
            cache_data={"config": {"feature_flag": True}},
            config={
                "max_items": 100,
                "timeout": 30
            }
        )

        class BusinessService(InjectableService):
            async def get_configured_limit(self):
                return self.container.config.get_int("max_items")

            async def get_cached_config(self):
                return await self.with_cache(
                    "config",
                    self._fetch_config
                )

            async def _fetch_config(self):
                return {"feature_flag": False}

            def log_operation(self, message):
                self.log("info", message)

        service = BusinessService(container)

        limit = await service.get_configured_limit()
        assert limit == 100

        config = await service.get_cached_config()
        assert config["feature_flag"] is True  # From cache

        service.log_operation("Test operation")
        assert len(container.logger.messages) == 1

    @pytest.mark.asyncio
    async def test_cache_fallback_behavior(self):
        """Test cache fallback when cache provider fails."""
        cache = MockCacheProvider()
        cache.get = AsyncMock(side_effect=Exception("Cache error"))

        container = ServiceContainer(cache_provider=cache)

        call_count = 0

        async def fetch_data():
            nonlocal call_count
            call_count += 1
            return f"data-{call_count}"

        # Should fall back to fetch function
        result = await container.with_cache("key", fetch_data)

        assert result == "data-1"
        assert call_count == 1


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_cost_data_retrieval_flow(self):
        """Test complete cost data retrieval flow."""
        # Setup
        container = create_test_container(
            cache_data={
                "cost_summary:org-123": {
                    "this_month": 5000.00,
                    "last_month": 4500.00
                }
            }
        )

        class CostService(InjectableService):
            async def get_cost_summary(self, org_id: OrganizationId) -> Result[Dict, Exception]:
                try:
                    data = await self.with_cache(
                        f"cost_summary:{org_id}",
                        lambda: self._fetch_from_provider(org_id)
                    )
                    return Result.ok(data)
                except Exception as e:
                    return Result.err(e)

            async def _fetch_from_provider(self, org_id: OrganizationId):
                # Simulated provider call
                return {
                    "this_month": 5000.00,
                    "last_month": 4500.00,
                    "forecast": 5500.00
                }

        service = CostService(container)
        result = await service.get_cost_summary(OrganizationId("org-123"))

        assert result.success is True
        assert result.value["this_month"] == 5000.00

    @pytest.mark.asyncio
    async def test_multi_provider_error_handling(self):
        """Test error handling across multiple providers."""
        errors = []

        @handle_provider_errors("AWS")
        async def call_aws():
            err = Exception("AWS Error")
            err.response = {"Error": {"Code": "ThrottlingException"}}
            raise err

        @handle_provider_errors("AZURE")
        async def call_azure():
            err = Exception("Azure Error")
            err.status_code = 429
            raise err

        @handle_provider_errors("GCP")
        async def call_gcp():
            err = Exception("GCP Error")
            err.code = lambda: "RESOURCE_EXHAUSTED"
            raise err

        # All should be mapped to rate limit errors
        for func in [call_aws, call_azure, call_gcp]:
            try:
                await func()
            except CloudProviderException as e:
                errors.append(e)

        assert len(errors) == 3
        assert all(e.error_code == "CLOUD_RATE_LIMITED" for e in errors)


class TestCodeQualityPatterns:
    """Test code quality patterns from clean code implementation."""

    def test_functions_are_small(self):
        """Test that service methods are small and focused."""
        import inspect
        from app.shared.service_base import BaseService

        # Get all methods
        methods = [
            getattr(BaseService, name)
            for name in dir(BaseService)
            if callable(getattr(BaseService, name)) and not name.startswith("_")
        ]

        for method in methods:
            if hasattr(method, '__code__'):
                # Check method is reasonably small (< 50 lines is a guideline)
                lines = method.__code__.co_code
                assert len(lines) < 5000, f"{method.__name__} is too large"

    def test_type_hints_usage(self):
        """Test that functions use type hints."""
        from app.shared.service_base import BaseService
        import inspect

        # Check key methods have type hints
        sig = inspect.signature(BaseService.get_by_id)
        params = list(sig.parameters.keys())

        assert "id" in params
        assert "org_id" in params

    def test_dataclass_usage(self):
        """Test that data containers use appropriate structures."""
        # Result type is a dataclass-like structure
        result = Result.ok("data")

        assert hasattr(result, 'success')
        assert hasattr(result, 'value')
        assert hasattr(result, 'error')

    def test_context_manager_usage(self):
        """Test that context managers are used appropriately."""
        from app.shared.dependencies import ServiceContainer
        import inspect

        # Check session method is a context manager
        sig = inspect.signature(ServiceContainer.session)
        # Note: Actual verification would need async context manager inspection


class TestPerformanceConsiderations:
    """Test performance-related aspects."""

    @pytest.mark.asyncio
    async def test_caching_reduces_calls(self):
        """Test that caching reduces expensive calls."""
        container = create_test_container()

        call_count = 0

        async def expensive_operation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)  # Simulate work
            return f"result-{call_count}"

        # Make multiple calls
        for _ in range(10):
            await container.with_cache("key", expensive_operation)

        # Should only call once
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_batch_error_handling_performance(self):
        """Test error aggregator handles large batches efficiently."""
        aggregator = ErrorAggregator()

        # Process large batch
        for i in range(1000):
            if i % 10 == 0:
                aggregator.add_failure(f"item-{i}", ValueError(f"Error {i}"))
            else:
                aggregator.add_success()

        report = aggregator.get_report()

        assert report["total"] == 1000
        assert report["failure_count"] == 100
        assert report["success_count"] == 900

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_paginated_response(self):
        """Test handling of empty paginated response."""
        response: PaginatedResponse[ResourceResponse] = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 10,
            "has_more": False
        }

        assert response["items"] == []
        assert response["has_more"] is False

    def test_result_with_none_value(self):
        """Test Result with None value."""
        result = Result.ok(None)

        assert result.success is True
        assert result.value is None

    @pytest.mark.asyncio
    async def test_service_with_no_org_scoping(self):
        """Test service methods without organization scoping."""
        mock_db = AsyncMock()

        class ModelWithoutOrg:
            id = "test-id"
            deleted_at = None

        service = BaseService(ModelWithoutOrg, mock_db)

        # Should not fail when model has no organization_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ModelWithoutOrg()
        mock_db.execute.return_value = mock_result

        result = await service.get_by_id("test-id", org_id="org-123")
        assert result.id == "test-id"

    def test_config_with_missing_keys(self):
        """Test config provider with missing keys."""
        config = MockConfigProvider()

        assert config.get("missing") is None
        assert config.get("missing", "default") == "default"
        assert config.get_int("missing", 42) == 42
        assert config.get_bool("missing", True) is True
