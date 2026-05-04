"""Tests for cloud connector audit fixes.

Covers: SQL injection prevention, sanitization, retry logic,
circuit breaker narrowing, token refresh, blocking I/O wrapping,
input validation, cache bounds, KeyRotator, and credential cache cleanup.
"""

import asyncio
import re
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cloud_accounts.adapters.analytics_base import (
    AnalyticsAdapterBase,
    validate_sql_identifier,
    validate_group_by_fields,
    validate_query_params,
)
from app.shared.circuit_breaker import CircuitBreaker, CircuitState, _TRANSIENT_EXCEPTIONS
from app.shared.exceptions import (
    BadRequestError,
    CloudProviderException,
    RateLimitException,
)
from app.shared.key_rotation import KeyRotator
from app.shared.rate_limit import check_rate_limit
from app.shared.retry import RetryConfig, RetryContext, is_retryable_csp_error


# ── SQL Injection Prevention ──────────────────────────────────────────────

class TestValidateSqlIdentifier:
    def test_valid_identifiers(self):
        assert validate_sql_identifier("my_table") == "my_table"
        assert validate_sql_identifier("schema.table") == "schema.table"
        assert validate_sql_identifier("_private") == "_private"
        assert validate_sql_identifier("tbl123") == "tbl123"

    def test_rejects_semicolon(self):
        with pytest.raises(BadRequestError, match="disallowed characters"):
            validate_sql_identifier("tbl; DROP TABLE")

    def test_rejects_sql_comment(self):
        with pytest.raises(BadRequestError, match="disallowed characters"):
            validate_sql_identifier("tbl--comment")

    def test_rejects_space(self):
        with pytest.raises(BadRequestError, match="disallowed characters"):
            validate_sql_identifier("tbl name")

    def test_rejects_empty(self):
        with pytest.raises(BadRequestError, match="empty identifier|disallowed characters"):
            validate_sql_identifier("")

    def test_rejects_quote(self):
        with pytest.raises(BadRequestError, match="disallowed characters"):
            validate_sql_identifier("tbl'name")


class TestValidateGroupByFields:
    ALLOWED = [
        "invoice_month", "service_name", "resource_type",
        "region", "resource_id", "project_name",
        "usage_start_date", "usage_end_date",
    ]

    def test_allowed_fields_pass(self):
        result = validate_group_by_fields(self.ALLOWED)
        assert result == self.ALLOWED

    def test_rejects_unknown_field(self):
        with pytest.raises(BadRequestError, match="Invalid group_by"):
            validate_group_by_fields(["service_name", "evil_injection"])

    def test_empty_list_passes(self):
        assert validate_group_by_fields([]) == []


class TestValidateQueryParams:
    def test_valid_dates(self):
        # Should not raise
        validate_query_params("2024-01-01", "2024-06-30")

    def test_invalid_start_date_format(self):
        with pytest.raises(BadRequestError, match="start_date"):
            validate_query_params("not-a-date", "2024-06-30")

    def test_invalid_end_date_format(self):
        with pytest.raises(BadRequestError, match="end_date"):
            validate_query_params("2024-01-01", "bad")

    def test_start_after_end(self):
        with pytest.raises(BadRequestError, match="start_date"):
            validate_query_params("2024-12-01", "2024-01-01")

    def test_range_too_large(self):
        with pytest.raises(BadRequestError, match="exceeds"):
            validate_query_params("2023-01-01", "2025-01-01")


# ── Sanitization ──────────────────────────────────────────────────────────

class TestSanitizeCspError:
    def test_redacts_aws_account_id(self):
        from app.cloud_accounts.adapters.aws import _sanitize_csp_error
        err = Exception("Access denied for account 123456789012")
        result = _sanitize_csp_error(err)
        assert "123456789012" not in result
        assert "***REDACTED***" in result

    def test_redacts_arn(self):
        from app.cloud_accounts.adapters.aws import _sanitize_csp_error
        err = Exception("arn:aws:iam::123456789012:user/admin")
        result = _sanitize_csp_error(err)
        # The account ID in the ARN should be redacted
        assert "123456789012" not in result
        assert "***REDACTED***" in result

    def test_returns_sanitized_not_hardcoded(self):
        from app.cloud_accounts.adapters.aws import _sanitize_csp_error
        err = Exception("ThrottlingException for account 111222333444")
        result = _sanitize_csp_error(err)
        # Should NOT return the old hardcoded message
        assert result != "Cloud provider API error. Check server logs for details."
        assert "ThrottlingException" in result


class TestSanitizeConnectionError:
    def test_redacts_access_token(self):
        err = Exception("ODBC Driver 17: ACCESSTOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs")
        config = {"server": "myserver.database.windows.net"}
        result = AnalyticsAdapterBase.sanitize_connection_error(err, config)
        # The token value should be redacted (key name may remain)
        assert "eyJ0eXAi" not in result
        assert "REDACTED" in result

    def test_redacts_aws_keys(self):
        err = Exception("InvalidClientTokenId: AKIAIOSFODNN7EXAMPLE")
        config = {"access_key_id": "AKIAIOSFODNN7EXAMPLE"}
        result = AnalyticsAdapterBase.sanitize_connection_error(err, config)
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_redacts_password(self):
        err = Exception("Login failed for user: password=SuperSecret123!")
        config = {}
        result = AnalyticsAdapterBase.sanitize_connection_error(err, config)
        assert "SuperSecret123" not in result


# ── Retry Logic ────────────────────────────────────────────────────────────

class TestIsRetryableCspError:
    def test_connection_error_retryable(self):
        assert is_retryable_csp_error(ConnectionError("refused")) is True

    def test_timeout_error_retryable(self):
        assert is_retryable_csp_error(TimeoutError("timed out")) is True

    def test_rate_limit_exception_retryable(self):
        assert is_retryable_csp_error(RateLimitException("429", retry_after=10)) is True

    def test_cloud_provider_retryable_flag(self):
        err = CloudProviderException("aws", "transient", retryable=True)
        assert is_retryable_csp_error(err) is True

    def test_cloud_provider_not_retryable(self):
        err = CloudProviderException("aws", "AccessDenied", retryable=False)
        assert is_retryable_csp_error(err) is False

    def test_boto3_throttling_retryable(self):
        err = Exception("ThrottlingException: Rate exceeded")
        assert is_retryable_csp_error(err) is True

    def test_boto3_access_denied_not_retryable(self):
        err = Exception("AccessDenied: Not authorized")
        assert is_retryable_csp_error(err) is False

    def test_429_in_message_retryable(self):
        assert is_retryable_csp_error(Exception("HTTP 429 Too Many Requests")) is True

    def test_boto3_client_error_with_retryable_code(self):
        err = MagicMock()
        err.response = {
            "Error": {"Code": "ThrottlingException"},
            "ResponseMetadata": {"HTTPStatusCode": 400},
        }
        assert is_retryable_csp_error(err) is True

    def test_boto3_client_error_503_retryable(self):
        err = MagicMock()
        err.response = {
            "Error": {"Code": "ServiceUnavailable"},
            "ResponseMetadata": {"HTTPStatusCode": 503},
        }
        assert is_retryable_csp_error(err) is True


class TestRetryContextShouldRetry:
    def test_uses_is_retryable_csp_error(self):
        config = RetryConfig(max_attempts=3, retryable_exceptions=(ValueError,))
        ctx = RetryContext(config)
        ctx.attempt = 1
        # ConnectionError not in retryable_exceptions but is_retryable_csp_error returns True
        assert ctx.should_retry(ConnectionError("fail")) is True

    def test_non_retryable_stops(self):
        config = RetryConfig(max_attempts=3, retryable_exceptions=(ValueError,))
        ctx = RetryContext(config)
        ctx.attempt = 1
        # BadRequestError is not retryable by any heuristic
        assert ctx.should_retry(BadRequestError("bad input")) is False


# ── Circuit Breaker ────────────────────────────────────────────────────────

class TestCircuitBreakerExpectedExceptions:
    def test_transient_exceptions_narrow(self):
        assert Exception not in _TRANSIENT_EXCEPTIONS
        assert ConnectionError in _TRANSIENT_EXCEPTIONS
        assert TimeoutError in _TRANSIENT_EXCEPTIONS
        assert CloudProviderException in _TRANSIENT_EXCEPTIONS
        assert RateLimitException in _TRANSIENT_EXCEPTIONS

    @pytest.mark.asyncio
    async def test_bad_request_does_not_trip_breaker(self):
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            expected_exceptions=_TRANSIENT_EXCEPTIONS,
        )
        try:
            await breaker.call(lambda: _raise(BadRequestError("bad")))
        except BadRequestError:
            pass
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_cloud_provider_trips_breaker(self):
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            expected_exceptions=_TRANSIENT_EXCEPTIONS,
        )
        try:
            await breaker.call(lambda: _raise(CloudProviderException("aws", "fail")))
        except CloudProviderException:
            pass
        assert breaker.failure_count == 1


# ── KeyRotator ─────────────────────────────────────────────────────────────

class TestKeyRotatorEncrypt:
    @patch("app.shared.key_rotation.encrypt", return_value="ENC_VAL")
    def test_encrypt_string(self, mock_enc):
        rotator = KeyRotator(primary_key="test-key")
        result = rotator.encrypt("hello")
        mock_enc.assert_called_once_with("hello")
        assert result == "v0:ENC_VAL"

    @patch("app.shared.key_rotation.encrypt", return_value="ENC_VAL")
    def test_encrypt_bytes(self, mock_enc):
        rotator = KeyRotator(primary_key="test-key")
        result = rotator.encrypt(b"hello")
        mock_enc.assert_called_once_with("hello")
        assert result == "v0:ENC_VAL"


# ── Rate Limiting ──────────────────────────────────────────────────────────

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        # Fresh key should always pass
        await check_rate_limit("test:under_limit", max_requests=5, window_seconds=60)

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        key = f"test:over_limit_{time.time()}"
        for _ in range(3):
            await check_rate_limit(key, max_requests=3, window_seconds=60)
        with pytest.raises(BadRequestError, match="Rate limit exceeded"):
            await check_rate_limit(key, max_requests=3, window_seconds=60)


# ── Credential Cache Cleanup ──────────────────────────────────────────────

class TestCredentialCacheCleanup:
    def test_cleanup_removes_expired(self):
        from app.cloud_accounts.credential_cache import SecureCredentialCache
        from app.shared.utils.time import utc_now
        cache = SecureCredentialCache(ttl_seconds=300)
        # Manually insert an expired entry (offset-aware)
        cache._memory_cache["expired_key"] = {
            "credentials": {"test": True},
            "expires_at": utc_now() - timedelta(seconds=60),
        }
        # Insert a valid entry
        cache._memory_cache["valid_key"] = {
            "credentials": {"test": True},
            "expires_at": utc_now() + timedelta(seconds=300),
        }
        removed = cache._cleanup_expired()
        assert removed == 1
        assert "expired_key" not in cache._memory_cache
        assert "valid_key" in cache._memory_cache


# ── Service Layer Analytics Integration ────────────────────────────────────

class TestServiceAnalyticsIntegration:
    def test_analytics_adapter_map_has_all_types(self):
        from app.cloud_accounts.service import ANALYTICS_ADAPTER_MAP, ANALYTICS_TYPES
        from app.shared.enums import CloudType
        assert CloudType.ATHENA in ANALYTICS_TYPES
        assert CloudType.BIGQUERY in ANALYTICS_TYPES
        assert CloudType.REDSHIFT in ANALYTICS_TYPES
        assert CloudType.SYNAPSE in ANALYTICS_TYPES

    def test_analytics_adapter_map_uses_lazy_import_paths(self):
        from app.cloud_accounts.service import ANALYTICS_ADAPTER_MAP
        for ctype, import_path in ANALYTICS_ADAPTER_MAP.items():
            assert isinstance(import_path, str)
            assert "." in import_path
            module_path, class_name = import_path.rsplit(".", 1)
            assert module_path.startswith("app.cloud_accounts.adapters.")
            assert class_name.endswith("Adapter")

    def test_get_adapter_returns_csp_types(self):
        from app.cloud_accounts.service import _get_adapter
        from app.cloud_accounts.adapters.aws import AWSAdapter
        from app.cloud_accounts.adapters.azure import AzureAdapter
        from app.shared.enums import CloudType

        for ctype, adapter_cls in [(CloudType.AWS, AWSAdapter), (CloudType.AZURE, AzureAdapter)]:
            config = _make_csp_config(ctype)
            account = _make_cloud_account(ctype, config)
            adapter = _get_adapter(account)
            assert isinstance(adapter, adapter_cls)


# ── TTLCache in Router ─────────────────────────────────────────────────────

class TestRouterTTLCache:
    def test_caches_are_ttl_cache(self):
        from cachetools import TTLCache
        # Import at runtime to avoid module-level side effects
        import app.cloud_accounts.router as router_mod
        assert isinstance(router_mod._live_data_cache, TTLCache)
        assert isinstance(router_mod._permission_cache, TTLCache)
        assert router_mod._live_data_cache.maxsize == 500
        assert router_mod._permission_cache.maxsize == 500


# ── Helper functions ────────────────────────────────────────────────────────

async def _raise(exc):
    raise exc


def _make_analytics_config(cloud_type):
    """Create a minimal valid config for an analytics adapter type."""
    from app.shared.enums import CloudType
    if cloud_type == CloudType.ATHENA:
        return {
            "database": "cost_db",
            "output_location": "s3://bucket/output/",
            "region": "us-east-1",
            "access_key_id": "AKIA_TEST",
            "secret_access_key": "SECRET_TEST",
        }
    elif cloud_type == CloudType.BIGQUERY:
        return {
            "project_id": "test-project",
            "dataset_id": "cost_dataset",
            "credentials_json": '{"type": "service_account"}',
        }
    elif cloud_type == CloudType.REDSHIFT:
        return {
            "cluster_identifier": "test-cluster",
            "database": "cost_db",
            "access_key_id": "AKIA_TEST",
            "secret_access_key": "SECRET_TEST",
            "region": "us-east-1",
        }
    elif cloud_type == CloudType.SYNAPSE:
        return {
            "server": "testserver.database.windows.net",
            "database": "cost_db",
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "00000000-0000-0000-0000-000000000000",
            "client_secret": "test-secret",
        }
    return {}


def _make_csp_config(cloud_type):
    """Create a minimal valid config for a CSP adapter type."""
    from app.shared.enums import CloudType
    if cloud_type == CloudType.AWS:
        return {
            "access_key_id": "AKIA_TEST",
            "secret_access_key": "SECRET_TEST",
            "region": "us-east-1",
        }
    elif cloud_type == CloudType.AZURE:
        return {
            "subscription_id": "00000000-0000-0000-0000-000000000000",
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "00000000-0000-0000-0000-000000000000",
            "client_secret": "test-secret",
        }
    return {}


def _make_cloud_account(cloud_type, config):
    """Create a mock CloudAccount with encrypted config."""
    from app.shared.crypto import encrypt
    from app.shared.enums import CloudType
    import json
    account = MagicMock()
    account.type = cloud_type
    account.config = encrypt(json.dumps(config))
    return account
