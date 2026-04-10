"""Tests for Redshift, Athena, and Synapse analytics connector adapters."""

import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cloud_accounts.adapters.redshift import RedshiftAdapter, RedshiftConfig
from app.cloud_accounts.adapters.athena import AthenaAdapter, AthenaConfig
from app.cloud_accounts.adapters.synapse import SynapseAdapter, SynapseConfig
from app.shared.enums import CloudType


# ===========================
# REDSHIFT TESTS
# ===========================

@pytest.fixture
def redshift_config():
    """Valid Redshift configuration."""
    return {
        "cluster_id": "my-cluster",
        "database": "dev",
        "table_name": "aws_billing",
        "host": "my-cluster.xxxxxx.region.redshift.amazonaws.com",
        "port": 5439,
        "region": "us-east-1",
        "iam_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "iam_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    }


class TestRedshiftConfig:
    """Test Redshift configuration validation."""
    
    def test_valid_config(self, redshift_config):
        config = RedshiftConfig(redshift_config)
        assert config.cluster_id == "my-cluster"
        assert config.database == "dev"
        assert config.table_name == "aws_billing"
    
    def test_missing_required_fields(self):
        config = {"cluster_id": "my-cluster"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            RedshiftConfig(config)
    
    def test_fully_qualified_table(self, redshift_config):
        config = RedshiftConfig(redshift_config)
        assert config.get_fully_qualified_table() == "aws_billing"
    
    def test_fully_qualified_table_with_schema(self, redshift_config):
        redshift_config["schema"] = "billing"
        config = RedshiftConfig(redshift_config)
        assert config.get_fully_qualified_table() == "billing.aws_billing"


class TestRedshiftAdapter:
    """Test Redshift adapter functionality."""
    
    def test_platform_type(self, redshift_config):
        adapter = RedshiftAdapter(redshift_config)
        assert adapter.platform_type == CloudType.REDSHIFT
    
    @patch('app.cloud_accounts.adapters.redshift.boto3.Session')
    @pytest.mark.asyncio
    async def test_validate_credentials_success(self, mock_session, redshift_config):
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        mock_client.execute_statement.return_value = {"Id": "stmt-123"}
        mock_client.get_waiter.return_value.wait.return_value = None
        mock_client.get_statement_result.return_value = {
            "ColumnMetadata": [{"name": "row_count"}],
            "Records": [{"longValue": 1000}]
        }
        
        adapter = RedshiftAdapter(redshift_config)
        result = await adapter.validate_credentials()
        
        assert result["valid"] is True
        assert result["table_exists"] is True
    
    @patch('app.cloud_accounts.adapters.redshift.boto3.Session')
    @pytest.mark.asyncio
    async def test_validate_credentials_permission_denied(self, mock_session, redshift_config):
        from botocore.exceptions import ClientError
        
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        mock_client.execute_statement.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Permission denied"}},
            "ExecuteStatement"
        )
        
        adapter = RedshiftAdapter(redshift_config)
        result = await adapter.validate_credentials()
        
        assert result["valid"] is False
        assert len(result["permission_warnings"]) > 0


# ===========================
# ATHENA TESTS
# ===========================

@pytest.fixture
def athena_config():
    """Valid Athena configuration."""
    return {
        "database": "athena_billing",
        "table_name": "aws_billing_cur",
        "s3_output_location": "s3://my-bucket/athena-results/",
        "region": "us-east-1",
        "workgroup": "primary",
        "iam_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "iam_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    }


class TestAthenaConfig:
    """Test Athena configuration validation."""
    
    def test_valid_config(self, athena_config):
        config = AthenaConfig(athena_config)
        assert config.database == "athena_billing"
        assert config.table_name == "aws_billing_cur"
        assert config.s3_output_location == "s3://my-bucket/athena-results/"
    
    def test_missing_required_fields(self):
        config = {"database": "athena_billing"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            AthenaConfig(config)
    
    def test_fully_qualified_table(self, athena_config):
        config = AthenaConfig(athena_config)
        assert config.get_fully_qualified_table() == "athena_billing.aws_billing_cur"


class TestAthenaAdapter:
    """Test Athena adapter functionality."""
    
    def test_platform_type(self, athena_config):
        adapter = AthenaAdapter(athena_config)
        assert adapter.platform_type == CloudType.ATHENA
    
    @patch('app.cloud_accounts.adapters.athena.boto3.Session')
    @pytest.mark.asyncio
    async def test_validate_credentials_success(self, mock_session, athena_config):
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        mock_client.start_query_execution.return_value = {"QueryExecutionId": "query-123"}
        mock_client.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        mock_client.get_query_results.return_value = {
            "ResultSet": {
                "Rows": [
                    {"Data": [{"VarCharValue": "row_count"}]},
                    {"Data": [{"VarCharValue": "1000"}]}
                ]
            }
        }
        
        adapter = AthenaAdapter(athena_config)
        result = await adapter.validate_credentials()
        
        assert result["valid"] is True
        assert result["table_exists"] is True
    
    @patch('app.cloud_accounts.adapters.athena.boto3.Session')
    @pytest.mark.asyncio
    async def test_validate_credentials_permission_denied(self, mock_session, athena_config):
        from botocore.exceptions import ClientError
        
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        mock_client.start_query_execution.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Permission denied"}},
            "StartQueryExecution"
        )
        
        adapter = AthenaAdapter(athena_config)
        result = await adapter.validate_credentials()
        
        assert result["valid"] is False
        assert len(result["permission_warnings"]) > 0


# ===========================
# SYNAPSE TESTS
# ===========================

@pytest.fixture
def synapse_config():
    """Valid Synapse configuration."""
    return {
        "server": "my-synapse.sql.azuresynapse.net",
        "database": "CloudCosts",
        "table_name": "azure_billing",
        "tenant_id": "tenant-123",
        "client_id": "client-123",
        "client_secret": "secret-123",
        "port": 1433
    }


class TestSynapseConfig:
    """Test Synapse configuration validation."""
    
    def test_valid_config(self, synapse_config):
        config = SynapseConfig(synapse_config)
        assert config.server == "my-synapse.sql.azuresynapse.net"
        assert config.database == "CloudCosts"
        assert config.table_name == "azure_billing"
    
    def test_missing_required_fields(self):
        config = {"server": "my-synapse.sql.azuresynapse.net"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            SynapseConfig(config)
    
    def test_fully_qualified_table(self, synapse_config):
        config = SynapseConfig(synapse_config)
        assert config.get_fully_qualified_table() == "dbo.azure_billing"
    
    def test_fully_qualified_table_with_schema(self, synapse_config):
        synapse_config["schema"] = "billing"
        config = SynapseConfig(synapse_config)
        assert config.get_fully_qualified_table() == "billing.azure_billing"


class TestSynapseAdapter:
    """Test Synapse adapter functionality."""
    
    def test_platform_type(self, synapse_config):
        adapter = SynapseAdapter(synapse_config)
        assert adapter.platform_type == CloudType.SYNAPSE
    
    @pytest.mark.asyncio
    async def test_validate_credentials_success(self, synapse_config):
        with patch.object(SynapseAdapter, '_execute_query', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"row_count": 1000}]
            with patch.object(SynapseAdapter, '_check_table_schema', new_callable=AsyncMock) as mock_schema:
                mock_schema.return_value = True
                
                adapter = SynapseAdapter(synapse_config)
                result = await adapter.validate_credentials()
                
                assert result["valid"] is True
                assert result["table_exists"] is True
    
    @pytest.mark.asyncio
    async def test_validate_credentials_auth_failed(self, synapse_config):
        from azure.core.exceptions import ClientAuthenticationError
        
        with patch.object(SynapseAdapter, '_execute_query', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = ClientAuthenticationError("Authentication failed")
            
            adapter = SynapseAdapter(synapse_config)
            result = await adapter.validate_credentials()
            
            assert result["valid"] is False
            assert len(result["permission_warnings"]) > 0


# ===========================
# INTEGRATION TESTS (require real credentials)
# ===========================

class TestAnalyticsIntegration:
    """Integration tests with real platforms (skipped by default)."""
    
    @pytest.mark.skipif(
        not os.environ.get("TEST_AWS_ACCESS_KEY_ID"),
        reason="Requires TEST_AWS_ACCESS_KEY_ID environment variable"
    )
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_redshift_real_connection(self):
        """Test connection to real Redshift (requires credentials)."""
        config = {
            "cluster_id": os.environ.get("TEST_REDSHIFT_CLUSTER"),
            "database": os.environ.get("TEST_REDSHIFT_DB", "dev"),
            "table_name": os.environ.get("TEST_REDSHIFT_TABLE", "aws_billing"),
            "iam_access_key_id": os.environ["TEST_AWS_ACCESS_KEY_ID"],
            "iam_secret_access_key": os.environ["TEST_AWS_SECRET_ACCESS_KEY"],
            "region": os.environ.get("TEST_AWS_REGION", "us-east-1")
        }
        
        adapter = RedshiftAdapter(config)
        try:
            result = await adapter.validate_credentials()
            assert "valid" in result
        except Exception as e:
            assert False, f"Integration test crashed: {e}"
        finally:
            await adapter.close()
    
    @pytest.mark.skipif(
        not os.environ.get("TEST_AWS_ACCESS_KEY_ID"),
        reason="Requires TEST_AWS_ACCESS_KEY_ID environment variable"
    )
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_athena_real_connection(self):
        """Test connection to real Athena (requires credentials)."""
        config = {
            "database": os.environ.get("TEST_ATHENA_DB", "athena_billing"),
            "table_name": os.environ.get("TEST_ATHENA_TABLE", "aws_billing_cur"),
            "s3_output_location": os.environ.get("TEST_ATHENA_S3", "s3://test/results/"),
            "iam_access_key_id": os.environ["TEST_AWS_ACCESS_KEY_ID"],
            "iam_secret_access_key": os.environ["TEST_AWS_SECRET_ACCESS_KEY"],
            "region": os.environ.get("TEST_AWS_REGION", "us-east-1")
        }
        
        adapter = AthenaAdapter(config)
        try:
            result = await adapter.validate_credentials()
            assert "valid" in result
        except Exception as e:
            assert False, f"Integration test crashed: {e}"
        finally:
            await adapter.close()
    
    @pytest.mark.skipif(
        not os.environ.get("TEST_AZURE_TENANT_ID"),
        reason="Requires TEST_AZURE_TENANT_ID environment variable"
    )
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_synapse_real_connection(self):
        """Test connection to real Synapse (requires credentials)."""
        config = {
            "server": os.environ.get("TEST_SYNAPSE_SERVER", "test.sql.azuresynapse.net"),
            "database": os.environ.get("TEST_SYNAPSE_DB", "CloudCosts"),
            "table_name": os.environ.get("TEST_SYNAPSE_TABLE", "azure_billing"),
            "tenant_id": os.environ["TEST_AZURE_TENANT_ID"],
            "client_id": os.environ.get("TEST_AZURE_CLIENT_ID", "test-client"),
            "client_secret": os.environ.get("TEST_AZURE_CLIENT_SECRET", "test-secret")
        }
        
        adapter = SynapseAdapter(config)
        try:
            result = await adapter.validate_credentials()
            assert "valid" in result
        except Exception as e:
            assert False, f"Integration test crashed: {e}"
        finally:
            await adapter.close()
