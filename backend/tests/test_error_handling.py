"""Comprehensive tests for unified error handling.

This module tests all features of the error handling module:
- ProviderErrorMapper for AWS, Azure, GCP
- handle_provider_errors decorator
- ErrorAggregator for batch operations
"""

import pytest
from unittest.mock import Mock, patch

from app.shared.error_handling import (
    ProviderErrorMapper,
    handle_provider_errors,
    ErrorAggregator,
)
from app.shared.exceptions import (
    CloudProviderException,
    ValidationException,
    NotFoundError,
)


class TestProviderErrorMapperAWS:
    """Test AWS error mapping."""

    def test_access_denied_exception(self):
        """Test AccessDeniedException mapping."""
        error = ProviderErrorMapper.map_aws_error(
            "AccessDeniedException",
            "Access denied"
        )

        assert error.error_code == "CLOUD_PERMISSION_DENIED"
        assert "permissions insufficient" in error.message
        assert error.retryable is False

    def test_throttling_exception(self):
        """Test ThrottlingException mapping."""
        error = ProviderErrorMapper.map_aws_error(
            "ThrottlingException",
            "Rate exceeded"
        )

        assert error.error_code == "CLOUD_RATE_LIMITED"
        assert error.retryable is True

    def test_service_unavailable_exception(self):
        """Test ServiceUnavailableException mapping."""
        error = ProviderErrorMapper.map_aws_error(
            "ServiceUnavailableException",
            "Service unavailable"
        )

        assert error.error_code == "CLOUD_SERVICE_UNAVAILABLE"
        assert error.retryable is True

    def test_invalid_parameter_exception(self):
        """Test InvalidParameterException mapping."""
        error = ProviderErrorMapper.map_aws_error(
            "InvalidParameterException",
            "Invalid parameter"
        )

        assert error.error_code == "CLOUD_INVALID_PARAMETER"
        assert error.retryable is False

    def test_unknown_error(self):
        """Test unknown AWS error mapping."""
        error = ProviderErrorMapper.map_aws_error(
            "UnknownError",
            "Something went wrong"
        )

        assert error.error_code == "CLOUD_PROVIDER_ERROR"
        assert "AWS API error" in error.message

    def test_opt_in_required(self):
        """Test OptInRequired mapping."""
        error = ProviderErrorMapper.map_aws_error(
            "OptInRequired",
            "Opt-in required"
        )

        assert error.error_code == "CLOUD_OPT_IN_REQUIRED"
        assert error.retryable is False

    def test_endpoint_connection_error(self):
        """Test EndpointConnectionError mapping."""
        error = ProviderErrorMapper.map_aws_error(
            "EndpointConnectionError",
            "Connection failed"
        )

        assert error.error_code == "CLOUD_CONNECTION_ERROR"
        assert error.retryable is True


class TestProviderErrorMapperAzure:
    """Test Azure error mapping."""

    def test_401_unauthorized(self):
        """Test 401 Unauthorized mapping."""
        error = ProviderErrorMapper.map_azure_error(401, "Unauthorized")

        assert error.error_code == "CLOUD_AUTH_FAILED"
        assert error.retryable is False

    def test_403_forbidden(self):
        """Test 403 Forbidden mapping."""
        error = ProviderErrorMapper.map_azure_error(403, "Forbidden")

        assert error.error_code == "CLOUD_ACCESS_DENIED"
        assert error.retryable is False

    def test_404_not_found(self):
        """Test 404 Not Found mapping."""
        error = ProviderErrorMapper.map_azure_error(404, "Not found")

        assert error.error_code == "CLOUD_RESOURCE_NOT_FOUND"
        assert error.retryable is False

    def test_429_rate_limited(self):
        """Test 429 Rate Limited mapping."""
        error = ProviderErrorMapper.map_azure_error(429, "Too many requests")

        assert error.error_code == "CLOUD_RATE_LIMITED"
        assert error.retryable is True

    def test_500_server_error(self):
        """Test 500 Server Error mapping."""
        error = ProviderErrorMapper.map_azure_error(500, "Internal error")

        assert error.error_code == "CLOUD_SERVER_ERROR"
        assert error.retryable is True

    def test_503_service_unavailable(self):
        """Test 503 Service Unavailable mapping."""
        error = ProviderErrorMapper.map_azure_error(503, "Service unavailable")

        assert error.error_code == "CLOUD_SERVICE_UNAVAILABLE"
        assert error.retryable is True

    def test_unknown_status_code(self):
        """Test unknown Azure status code mapping."""
        error = ProviderErrorMapper.map_azure_error(418, "I'm a teapot")

        assert error.error_code == "CLOUD_PROVIDER_ERROR"
        assert "Azure API error (418)" in error.message


class TestProviderErrorMapperGCP:
    """Test GCP error mapping."""

    def test_permission_denied(self):
        """Test PERMISSION_DENIED mapping."""
        error = ProviderErrorMapper.map_gcp_error("PERMISSION_DENIED", "No access")

        assert error.error_code == "CLOUD_PERMISSION_DENIED"
        assert error.retryable is False

    def test_unauthenticated(self):
        """Test UNAUTHENTICATED mapping."""
        error = ProviderErrorMapper.map_gcp_error("UNAUTHENTICATED", "Not authenticated")

        assert error.error_code == "CLOUD_AUTH_FAILED"
        assert error.retryable is False

    def test_resource_exhausted(self):
        """Test RESOURCE_EXHAUSTED mapping."""
        error = ProviderErrorMapper.map_gcp_error("RESOURCE_EXHAUSTED", "Quota exceeded")

        assert error.error_code == "CLOUD_RATE_LIMITED"
        assert error.retryable is True

    def test_unavailable(self):
        """Test UNAVAILABLE mapping."""
        error = ProviderErrorMapper.map_gcp_error("UNAVAILABLE", "Service down")

        assert error.error_code == "CLOUD_SERVICE_UNAVAILABLE"
        assert error.retryable is True

    def test_not_found(self):
        """Test NOT_FOUND mapping."""
        error = ProviderErrorMapper.map_gcp_error("NOT_FOUND", "Resource not found")

        assert error.error_code == "CLOUD_RESOURCE_NOT_FOUND"
        assert error.retryable is False

    def test_invalid_argument(self):
        """Test INVALID_ARGUMENT mapping."""
        error = ProviderErrorMapper.map_gcp_error("INVALID_ARGUMENT", "Bad request")

        assert error.error_code == "CLOUD_INVALID_PARAMETER"
        assert error.retryable is False

    def test_unknown_error(self):
        """Test unknown GCP error mapping."""
        error = ProviderErrorMapper.map_gcp_error("UNKNOWN_ERROR", "Unknown")

        assert error.error_code == "CLOUD_PROVIDER_ERROR"
        assert "GCP API error" in error.message


class TestHandleProviderErrorsDecorator:
    """Test handle_provider_errors decorator."""

    @pytest.mark.asyncio
    async def test_successful_function_no_error(self):
        """Test decorator passes through successful function."""
        @handle_provider_errors("AWS")
        async def successful_function():
            return "success"

        result = await successful_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_aws_error_mapping(self):
        """Test decorator maps AWS errors."""
        @handle_provider_errors("AWS")
        async def failing_function():
            error = Exception("AWS Error")
            error.response = {"Error": {"Code": "ThrottlingException"}}
            raise error

        with pytest.raises(CloudProviderException) as exc_info:
            await failing_function()

        assert exc_info.value.error_code == "CLOUD_RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_azure_error_mapping(self):
        """Test decorator maps Azure errors."""
        @handle_provider_errors("AZURE")
        async def failing_function():
            error = Exception("Azure Error")
            error.status_code = 429
            raise error

        with pytest.raises(CloudProviderException) as exc_info:
            await failing_function()

        assert exc_info.value.error_code == "CLOUD_RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_gcp_error_mapping(self):
        """Test decorator maps GCP errors."""
        @handle_provider_errors("GCP")
        async def failing_function():
            error = Exception("GCP Error")
            error.code = lambda: "RESOURCE_EXHAUSTED"
            raise error

        with pytest.raises(CloudProviderException) as exc_info:
            await failing_function()

        assert exc_info.value.error_code == "CLOUD_RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_already_standardized_exception_reraised(self):
        """Test already standardized exceptions are re-raised."""
        @handle_provider_errors("AWS")
        async def failing_function():
            raise CloudProviderException(
                provider="AWS",
                message="Already standardized",
                error_code="CUSTOM_ERROR"
            )

        with pytest.raises(CloudProviderException) as exc_info:
            await failing_function()

        assert exc_info.value.error_code == "CUSTOM_ERROR"

    @pytest.mark.asyncio
    async def test_unknown_provider_error(self):
        """Test decorator handles unknown provider."""
        @handle_provider_errors("UNKNOWN")
        async def failing_function():
            raise Exception("Unknown error")

        with pytest.raises(CloudProviderException) as exc_info:
            await failing_function()

        assert exc_info.value.error_code == "CLOUD_PROVIDER_ERROR"


class TestErrorAggregator:
    """Test ErrorAggregator for batch operations."""

    def test_aggregator_initialization(self):
        """Test aggregator initializes with zero counts."""
        aggregator = ErrorAggregator()

        assert aggregator.success_count == 0
        assert aggregator.failure_count == 0
        assert len(aggregator.errors) == 0

    def test_add_success(self):
        """Test adding success."""
        aggregator = ErrorAggregator()
        aggregator.add_success()

        assert aggregator.success_count == 1
        assert aggregator.failure_count == 0

    def test_add_failure(self):
        """Test adding failure."""
        aggregator = ErrorAggregator()
        error = Exception("Test error")
        aggregator.add_failure("item-1", error)

        assert aggregator.success_count == 0
        assert aggregator.failure_count == 1
        assert len(aggregator.errors) == 1
        assert aggregator.errors[0]["item_id"] == "item-1"

    def test_add_failure_with_details(self):
        """Test adding failure with details."""
        aggregator = ErrorAggregator()
        error = Exception("Test error")
        aggregator.add_failure("item-1", error, {"extra": "info"})

        assert aggregator.errors[0]["details"] == {"extra": "info"}

    def test_has_errors_true(self):
        """Test has_errors returns True when errors exist."""
        aggregator = ErrorAggregator()
        aggregator.add_failure("item-1", Exception("Error"))

        assert aggregator.has_errors() is True

    def test_has_errors_false(self):
        """Test has_errors returns False when no errors."""
        aggregator = ErrorAggregator()
        aggregator.add_success()

        assert aggregator.has_errors() is False

    def test_get_report(self):
        """Test getting error report."""
        aggregator = ErrorAggregator()
        aggregator.add_success()
        aggregator.add_success()
        aggregator.add_failure("item-1", Exception("Error 1"))
        aggregator.add_failure("item-2", Exception("Error 2"))

        report = aggregator.get_report()

        assert report["total"] == 4
        assert report["success_count"] == 2
        assert report["failure_count"] == 2
        assert report["success_rate"] == 0.5

    def test_get_report_with_errors(self):
        """Test getting report includes error details."""
        aggregator = ErrorAggregator()
        aggregator.add_failure("item-1", Exception("Error message"))

        report = aggregator.get_report(include_errors=True)

        assert "errors" in report
        assert len(report["errors"]) == 1
        assert report["errors"][0]["error"] == "Error message"

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        aggregator = ErrorAggregator()

        # 0/0 should be 0.0 to avoid division by zero
        assert aggregator.get_report()["success_rate"] == 0.0

        aggregator.add_success()
        assert aggregator.get_report()["success_rate"] == 1.0

        aggregator.add_failure("item", Exception("Error"))
        assert aggregator.get_report()["success_rate"] == 0.5

    def test_multiple_operations(self):
        """Test aggregator with multiple operations."""
        aggregator = ErrorAggregator()

        for i in range(10):
            if i % 2 == 0:
                aggregator.add_success()
            else:
                aggregator.add_failure(f"item-{i}", Exception(f"Error {i}"))

        assert aggregator.success_count == 5
        assert aggregator.failure_count == 5


class TestCloudProviderException:
    """Test CloudProviderException."""

    def test_exception_attributes(self):
        """Test exception has correct attributes."""
        exc = CloudProviderException(
            provider="AWS",
            message="Test error",
            error_code="TEST_ERROR",
            retryable=True
        )

        assert exc.provider == "AWS"
        assert "Test error" in exc.message
        assert exc.error_code == "TEST_ERROR"
        assert exc.retryable is True

    def test_exception_to_dict(self):
        """Test exception can be converted to dict."""
        exc = CloudProviderException(
            provider="AWS",
            message="Test error",
            error_code="TEST_ERROR"
        )

        result = exc.to_dict()

        assert result["error"]["code"] == "TEST_ERROR"
        assert "AWS" in result["error"]["message"]
        assert "error_id" in result["error"]

    def test_exception_str(self):
        """Test exception string representation."""
        exc = CloudProviderException(
            provider="AWS",
            message="Test error",
            error_code="TEST_ERROR"
        )

        assert "AWS: Test error" in str(exc)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_aws_error_without_response(self):
        """Test AWS error without response attribute."""
        @handle_provider_errors("AWS")
        async def failing_function():
            raise Exception("Generic error")

        # Should not crash
        with pytest.raises(CloudProviderException):
            import asyncio
            asyncio.run(failing_function())

    def test_azure_error_without_status_code(self):
        """Test Azure error without status_code."""
        error = ProviderErrorMapper.map_azure_error(None, "Unknown error")

        assert error.error_code == "CLOUD_PROVIDER_ERROR"

    def test_gcp_error_without_code(self):
        """Test GCP error without code."""
        error = ProviderErrorMapper.map_gcp_error(None, "Unknown error")

        assert error.error_code == "CLOUD_PROVIDER_ERROR"

    def test_error_aggregator_empty_report(self):
        """Test empty aggregator report."""
        aggregator = ErrorAggregator()
        report = aggregator.get_report()

        assert report["total"] == 0
        assert report["success_count"] == 0
        assert report["failure_count"] == 0

    def test_decorator_preserves_function_name(self):
        """Test decorator preserves function metadata."""
        @handle_provider_errors("AWS")
        async def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
