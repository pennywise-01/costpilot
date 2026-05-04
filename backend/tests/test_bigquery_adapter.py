"""Tests for BigQuery analytics connector adapter."""

import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cloud_accounts.adapters.bigquery import BigQueryAdapter, BigQueryConfig
from app.shared.enums import CloudType
from app.shared.exceptions import BadRequestError


# --- Test Fixtures ---

@pytest.fixture
def bigquery_config():
    """Valid BigQuery configuration."""
    return {
        "project_id": "test-gcp-project",
        "dataset_id": "cloud_billing",
        "table_name": "gcp_billing_export",
        "service_account_key": json.dumps({
            "type": "service_account",
            "project_id": "test-gcp-project",
            "private_key_id": "key123",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MaU8xKwwKU9dHDff\n-----END RSA PRIVATE KEY-----\n",
            "client_email": "test@test-gcp-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }),
        "location": "US",
        "query_timeout": 120
    }


@pytest.fixture
def bigquery_config_no_key():
    """BigQuery configuration without service account key (uses ADC)."""
    return {
        "project_id": "test-gcp-project",
        "dataset_id": "cloud_billing",
        "table_name": "gcp_billing_export",
        "location": "US",
        "query_timeout": 120
    }


@pytest.fixture
def mock_bigquery_row():
    """Mock BigQuery row object."""
    row = MagicMock()
    row.__iter__ = lambda self: iter(["invoice_month", "service_name", "total_cost"])
    row.keys.return_value = ["invoice_month", "service_name", "total_cost"]
    row.invoice_month = "2026-04"
    row.service_name = "Compute Engine"
    row.total_cost = 150.50
    return dict(row) if hasattr(row, 'items') else {
        "invoice_month": "2026-04",
        "service_name": "Compute Engine",
        "total_cost": 150.50
    }


@pytest.fixture
def mock_query_job():
    """Mock BigQuery query job."""
    job = MagicMock()
    
    # Mock rows with row_count attribute (BigQuery Row objects)
    mock_row = MagicMock()
    mock_row.row_count = 42
    mock_row.__getitem__ = lambda self, key: {"invoice_month": "2026-04", "service_name": "Compute Engine", "total_cost": 150.50}[key]
    mock_row.keys.return_value = ["invoice_month", "service_name", "total_cost"]
    job.result.return_value = [mock_row]
    job.done.return_value = True
    return job


# --- Unit Tests ---

class TestBigQueryConfig:
    """Test BigQuery configuration validation."""
    
    def test_valid_config(self, bigquery_config):
        """Test valid configuration passes validation."""
        config = BigQueryConfig(bigquery_config)
        assert config.project_id == "test-gcp-project"
        assert config.dataset_id == "cloud_billing"
        assert config.table_name == "gcp_billing_export"
    
    def test_missing_project_id(self):
        """Test missing project_id raises error."""
        config = {
            "dataset_id": "cloud_billing",
            "table_name": "gcp_billing_export"
        }
        with pytest.raises(ValueError, match="Missing required configuration"):
            BigQueryConfig(config)
    
    def test_missing_table_name(self):
        """Test missing table_name raises error."""
        config = {
            "project_id": "test-gcp-project",
            "dataset_id": "cloud_billing"
        }
        with pytest.raises(ValueError, match="Missing required configuration"):
            BigQueryConfig(config)
    
    def test_fully_qualified_table(self, bigquery_config):
        """Test fully qualified table name generation."""
        config = BigQueryConfig(bigquery_config)
        assert config.get_fully_qualified_table() == "`test-gcp-project.cloud_billing.gcp_billing_export`"
    
    def test_defaults(self):
        """Test default values are set correctly."""
        config = BigQueryConfig({
            "project_id": "test",
            "dataset_id": "test",
            "table_name": "test"
        })
        assert config.location == "US"
        assert config.query_timeout == 120


class TestBigQueryAdapter:
    """Test BigQuery adapter functionality."""
    
    def test_platform_type(self, bigquery_config):
        """Test platform type is set correctly."""
        adapter = BigQueryAdapter(bigquery_config)
        assert adapter.platform_type == CloudType.BIGQUERY
    
    @pytest.mark.asyncio
    async def test_validate_credentials_success(self, bigquery_config_no_key, mock_query_job):
        """Test successful credential validation."""
        mock_client = MagicMock()
        mock_client.query.return_value = mock_query_job
        mock_schema_cost = MagicMock()
        mock_schema_cost.name = "cost"
        mock_schema_usage = MagicMock()
        mock_schema_usage.name = "usage_start_date"
        mock_schema_invoice = MagicMock()
        mock_schema_invoice.name = "invoice_month"
        mock_client.get_table.return_value = MagicMock(
            schema=[mock_schema_cost, mock_schema_usage, mock_schema_invoice]
        )
        
        adapter = BigQueryAdapter(bigquery_config_no_key)
        with patch.object(adapter, '_get_client', return_value=mock_client):
            result = await adapter.validate_credentials()
        
        assert result["valid"] is True, f"validate_credentials returned: {result}"
        assert result["table_exists"] is True
        assert result["schema_valid"] is True
    
    @patch('app.cloud_accounts.adapters.bigquery.bigquery.Client')
    @pytest.mark.asyncio
    async def test_validate_credentials_table_not_found(self, mock_client_cls, bigquery_config_no_key):
        """Test validation when table doesn't exist."""
        from google.api_core.exceptions import NotFound
        
        mock_client = MagicMock()
        mock_client.query.side_effect = NotFound("Table not found")
        mock_client_cls.return_value = mock_client
        
        adapter = BigQueryAdapter(bigquery_config_no_key)
        result = await adapter.validate_credentials()
        
        assert result["valid"] is False
        assert result["table_exists"] is False
    
    @patch('app.cloud_accounts.adapters.bigquery.bigquery.Client')
    @pytest.mark.asyncio
    async def test_validate_credentials_permission_denied(self, mock_client_cls, bigquery_config_no_key):
        """Test validation when permissions are insufficient."""
        from google.api_core.exceptions import Forbidden
        
        mock_client = MagicMock()
        mock_client.query.side_effect = Forbidden("Permission denied")
        mock_client_cls.return_value = mock_client
        
        adapter = BigQueryAdapter(bigquery_config_no_key)
        result = await adapter.validate_credentials()
        
        assert result["valid"] is False
        assert "permission_warnings" in result
        assert len(result["permission_warnings"]) > 0
    
    @patch('app.cloud_accounts.adapters.bigquery.bigquery.Client')
    @pytest.mark.asyncio
    async def test_get_cost_and_usage(self, mock_client_cls, bigquery_config_no_key, mock_query_job):
        """Test cost and usage query execution."""
        mock_client = MagicMock()
        mock_rows = [
            {"invoice_month": "2026-04", "service_name": "Compute Engine", "total_cost": 150.50},
            {"invoice_month": "2026-04", "service_name": "Cloud Storage", "total_cost": 50.25}
        ]
        mock_query_job.result.return_value = mock_rows
        mock_client.query.return_value = mock_query_job
        mock_client_cls.return_value = mock_client
        
        adapter = BigQueryAdapter(bigquery_config_no_key)
        result = await adapter.get_cost_and_usage("2026-04-01", "2026-04-30")
        
        assert "columns" in result
        assert "rows" in result
        assert len(result["rows"]) == 2
        assert result["rows"][0]["total_cost"] == 150.50
    
    @patch('app.cloud_accounts.adapters.bigquery.bigquery.Client')
    @pytest.mark.asyncio
    async def test_get_monthly_cost_summary(self, mock_client_cls, bigquery_config_no_key):
        """Test monthly cost summary aggregation."""
        mock_client = MagicMock()
        mock_rows = [
            {"invoice_month": "2026-04", "month_cost": 500.00},
            {"invoice_month": "2026-03", "month_cost": 450.00}
        ]
        mock_job = MagicMock()
        mock_job.result.return_value = mock_rows
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client
        
        adapter = BigQueryAdapter(bigquery_config_no_key)
        result = await adapter.get_monthly_cost_summary()
        
        assert "this_month" in result
        assert "last_month" in result
        assert "forecast" in result
        assert result["this_month"] >= 0
        assert result["last_month"] == 450.00
    
    @patch('app.cloud_accounts.adapters.bigquery.bigquery.Client')
    @pytest.mark.asyncio
    async def test_get_daily_costs(self, mock_client_cls, bigquery_config_no_key):
        """Test daily cost retrieval."""
        mock_client = MagicMock()
        mock_rows = [
            {"date": "2026-04-01", "cost": 25.50},
            {"date": "2026-04-02", "cost": 30.00}
        ]
        mock_job = MagicMock()
        mock_job.result.return_value = mock_rows
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client
        
        adapter = BigQueryAdapter(bigquery_config_no_key)
        result = await adapter.get_daily_costs("2026-04-01", "2026-04-02")
        
        assert len(result) == 2
        assert result[0]["date"] == "2026-04-01"
        assert result[0]["cost"] == 25.50
    
    @patch('app.cloud_accounts.adapters.bigquery.bigquery.Client')
    @pytest.mark.asyncio
    async def test_discover_resources(self, mock_client_cls, bigquery_config_no_key):
        """Test resource discovery from billing table."""
        mock_client = MagicMock()
        mock_rows = [
            {
                "cloud_resource_id": "projects/test/instances/db1",
                "name": "projects/test/instances/db1",
                "resource_type": "Cloud SQL",
                "region": "us-central1",
                "state": "active",
                "project_name": "test-project"
            }
        ]
        mock_job = MagicMock()
        mock_job.result.return_value = mock_rows
        mock_client.query.return_value = mock_job
        mock_client_cls.return_value = mock_client
        
        adapter = BigQueryAdapter(bigquery_config_no_key)
        resources = await adapter.discover_resources()
        
        assert len(resources) == 1
        assert resources[0]["resource_type"] == "Cloud SQL"
        assert resources[0]["region"] == "us-central1"
    
    @pytest.mark.asyncio
    async def test_validate_table_schema_valid(self, bigquery_config_no_key):
        """Test schema validation when all columns present."""
        with patch.object(BigQueryAdapter, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_table = MagicMock()
            schema_fields = []
            for field_name in [
                "invoice_month", "usage_start_date", "usage_end_date",
                "cost", "currency", "service_name", "resource_type",
                "region", "resource_id", "project_name",
            ]:
                m = MagicMock()
                m.name = field_name
                schema_fields.append(m)
            mock_table.schema = schema_fields
            mock_client.get_table.return_value = mock_table
            mock_get_client.return_value = mock_client
            
            adapter = BigQueryAdapter(bigquery_config_no_key)
            result = await adapter.validate_table_schema()
            
            assert result["valid"] is True, f"validate_table_schema returned: {result}"
            assert len(result["missing_columns"]) == 0
    
    @pytest.mark.asyncio
    async def test_validate_table_schema_missing_columns(self, bigquery_config_no_key):
        """Test schema validation when columns are missing."""
        with patch.object(BigQueryAdapter, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_table = MagicMock()
            mock_table.schema = [
                MagicMock(name="cost")  # Only cost, missing usage_start_date
            ]
            mock_client.get_table.return_value = mock_table
            mock_get_client.return_value = mock_client
            
            adapter = BigQueryAdapter(bigquery_config_no_key)
            result = await adapter.validate_table_schema()
            
            assert result["valid"] is False
            assert "usage_start_date" in result["missing_columns"]
    
    def test_sanitize_connection_error_hides_aws_keys(self):
        """Test that AWS access keys are sanitized."""
        error_msg = "Connection failed with key AKIAIOSFODNN7EXAMPLE in config"
        sanitized = BigQueryAdapter.sanitize_connection_error(Exception(error_msg), {})
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
        assert "[REDACTED_AWS_KEY]" in sanitized
    
    def test_sanitize_connection_error_hides_private_keys(self):
        """Test that GCP private keys are sanitized."""
        error_msg = 'Error with private_key: "MIIEpAIBAAKCAQEA..." in request'
        sanitized = BigQueryAdapter.sanitize_connection_error(Exception(error_msg), {})
        assert "MIIEpAIBAAKCAQEA" not in sanitized
        assert "[REDACTED]" in sanitized
    
    def test_sanitize_connection_error_hides_secrets(self):
        """Test that generic secrets are sanitized."""
        error_msg = "Failed with client_secret: supersecret123 in auth"
        sanitized = BigQueryAdapter.sanitize_connection_error(Exception(error_msg), {})
        assert "supersecret123" not in sanitized
        assert "[REDACTED]" in sanitized
    
    def test_build_standard_query(self):
        """Test standard SQL query generation."""
        query = BigQueryAdapter.build_standard_query(
            table_ref="`project.dataset.table`",
            start_date="2026-04-01",
            end_date="2026-04-30",
            group_by=["service_name", "region"]
        )
        
        assert "`project.dataset.table`" in query
        assert "2026-04-01" in query
        assert "2026-04-30" in query
        assert "service_name" in query
        assert "region" in query
        assert "GROUP BY" in query
    
    def test_build_custom_query(self):
        """Test custom SQL query generation."""
        custom_sql = "SELECT * FROM table WHERE date >= '@start_date'"
        query = BigQueryAdapter.build_standard_query(
            table_ref="`project.dataset.table`",
            start_date="2026-04-01",
            end_date="2026-04-30",
            custom_sql=custom_sql
        )
        
        assert "2026-04-01" in query
        assert "@start_date" not in query  # Replaced
    
    @pytest.mark.asyncio
    async def test_close_client(self, bigquery_config):
        """Test client cleanup."""
        adapter = BigQueryAdapter(bigquery_config)
        adapter._client = MagicMock()
        
        await adapter.close()
        
        assert adapter._client is None


# --- Integration Tests (require real BigQuery) ---

class TestBigQueryIntegration:
    """Integration tests with real BigQuery (skipped by default)."""
    
    @pytest.mark.skipif(
        not os.environ.get("TEST_GCP_PROJECT"),
        reason="Requires TEST_GCP_PROJECT environment variable"
    )
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_connection(self):
        """Test connection to real BigQuery (requires credentials)."""
        config = {
            "project_id": os.environ["TEST_GCP_PROJECT"],
            "dataset_id": os.environ.get("TEST_BQ_DATASET", "cloud_billing"),
            "table_name": os.environ.get("TEST_BQ_TABLE", "gcp_billing_export"),
            "service_account_key": os.environ.get("TEST_GCP_SA_KEY")
        }
        
        adapter = BigQueryAdapter(config)
        try:
            result = await adapter.validate_credentials()
            # Should either succeed (valid creds) or fail gracefully
            assert "valid" in result
        except Exception as e:
            # Should not crash with unhandled exception
            assert False, f"Integration test crashed: {e}"
        finally:
            await adapter.close()
