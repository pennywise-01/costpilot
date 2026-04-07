"""Pytest fixtures for testing.

This module provides pytest fixtures for common testing scenarios.
"""

import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# from tests.factories import (
#     UserFactory,
#     OrganizationFactory,
#     EmployeeFactory,
#     CloudAccountFactory,
# )


# @pytest.fixture
# def test_user():
#     """Create a test user."""
#     return UserFactory()


# @pytest.fixture
# def test_organization():
#     """Create a test organization."""
#     return OrganizationFactory()


# @pytest.fixture
# def test_employee(test_user, test_organization):
#     """Create a test employee."""
#     return EmployeeFactory(user=test_user, organization=test_organization)


# @pytest.fixture
# def test_cloud_account(test_organization):
#     """Create a test cloud account."""
#     return CloudAccountFactory(organization=test_organization)


@pytest.fixture
def mock_aws_adapter():
    """Create a mock AWS adapter.

    Returns:
        Mock adapter with predefined responses
    """
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.validate_credentials.return_value = True
    mock.get_monthly_cost_summary.return_value = {
        "this_month": 1000.0,
        "last_month": 900.0,
        "forecast": 1100.0,
        "change_percent": 11.11
    }
    mock.get_regions.return_value = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2"
    ]
    mock.discover_resources.return_value = []
    return mock


@pytest.fixture
def mock_azure_adapter():
    """Create a mock Azure adapter."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.validate_credentials.return_value = True
    mock.get_monthly_cost_summary.return_value = {
        "this_month": 2000.0,
        "last_month": 1800.0,
        "forecast": 2200.0,
        "change_percent": 11.11
    }
    return mock


@pytest.fixture
def mock_gcp_adapter():
    """Create a mock GCP adapter."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.validate_credentials.return_value = True
    mock.get_monthly_cost_summary.return_value = {
        "this_month": 1500.0,
        "last_month": 1400.0,
        "forecast": 1600.0,
        "change_percent": 7.14
    }
    return mock


@pytest.fixture
def mock_cache():
    """Create a mock cache provider."""
    from app.shared.dependencies import MockCacheProvider
    return MockCacheProvider()


@pytest.fixture
def mock_config():
    """Create a mock config provider."""
    from app.shared.dependencies import MockConfigProvider
    return MockConfigProvider()


@pytest.fixture
def mock_logger():
    """Create a mock logger provider."""
    from app.shared.dependencies import MockLoggerProvider
    return MockLoggerProvider()


@pytest.fixture
def test_container(mock_cache, mock_config, mock_logger):
    """Create a test service container.

    Returns:
        ServiceContainer with mock providers
    """
    from app.shared.dependencies import ServiceContainer

    return ServiceContainer(
        cache_provider=mock_cache,
        config_provider=mock_config,
        logger_provider=mock_logger
    )


# @pytest.fixture
# async def db_session() -> AsyncGenerator[AsyncSession, None]:
#     """Create a test database session.
#
#     Yields:
#         AsyncSession for testing
#     """
#     engine = create_async_engine(
#         "postgresql+asyncpg://test:test@localhost/test",
#         echo=False
#     )
#     async_session = sessionmaker(
#         engine, class_=AsyncSession, expire_on_commit=False
#     )
#
#     async with async_session() as session:
#         yield session
#         await session.rollback()
#
#     await engine.dispose()


@pytest.fixture
def sample_csp_configs():
    """Provide sample CSP configurations for testing."""
    return {
        "aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "us-east-1"
        },
        "azure": {
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "client_id": "87654321-4321-4321-4321-210987654321",
            "client_secret": "test-secret",
            "subscription_id": "abcdef12-3456-7890-abcd-ef1234567890"
        },
        "gcp": {
            "project_id": "test-project",
            "credentials_json": '{"type": "service_account", "project_id": "test"}'
        }
    }


@pytest.fixture
def sample_cost_data():
    """Provide sample cost data for testing."""
    return [
        {"date": "2024-01-01", "cost": 100.0, "service": "EC2"},
        {"date": "2024-01-02", "cost": 150.0, "service": "EC2"},
        {"date": "2024-01-03", "cost": 120.0, "service": "S3"},
    ]


@pytest.fixture
def sample_resource_data():
    """Provide sample resource data for testing."""
    return [
        {
            "id": "i-1234567890abcdef0",
            "name": "test-instance",
            "type": "ec2",
            "region": "us-east-1",
            "status": "running",
            "cost_per_month": 50.0,
            "tags": {"Name": "test", "Environment": "dev"}
        },
        {
            "id": "i-0987654321fedcba0",
            "name": "test-instance-2",
            "type": "ec2",
            "region": "us-east-1",
            "status": "stopped",
            "cost_per_month": 0.0,
            "tags": {"Name": "test-2", "Environment": "dev"}
        }
    ]
