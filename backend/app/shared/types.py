"""Domain-specific types and typed dictionaries.

This module provides type definitions for improved type safety
and code clarity throughout the application.
"""

from typing import TypeVar, NewType, TypedDict, NotRequired, Generic, Any
from datetime import datetime
from decimal import Decimal


# Domain ID types - use NewType to prevent mixing different ID types
OrganizationId = NewType('OrganizationId', str)
UserId = NewType('UserId', str)
ResourceId = NewType('ResourceId', str)
CloudAccountId = NewType('CloudAccountId', str)
PoolId = NewType('PoolId', str)
RecommendationId = NewType('RecommendationId', str)

# Financial types
Money = NewType('Money', Decimal)
CurrencyCode = NewType('CurrencyCode', str)

# Generic result types
T = TypeVar('T')
E = TypeVar('E', bound=Exception)


class Result(Generic[T, E]):
    """Result type for operations that can fail.
    
    Provides a functional approach to error handling,
    avoiding exceptions for expected error cases.
    
    Usage:
        result = await some_operation()
        if result.success:
            data = result.value
        else:
            error = result.error
    """

    def __init__(self, success: bool, value: T | None = None, error: E | None = None):
        self.success = success
        self.value = value
        self.error = error

    @staticmethod
    def ok(value: T) -> "Result[T, None]":
        """Create a successful result."""
        return Result(True, value=value)

    @staticmethod
    def err(error: E) -> "Result[None, E]":
        """Create an error result."""
        return Result(False, error=error)

    def unwrap(self) -> T:
        """Get the value or raise if error.
        
        Raises:
            ValueError: If result is an error
        """
        if not self.success:
            raise ValueError("Cannot unwrap error result")
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the value or return default."""
        return self.value if self.success else default

    def map(self, func: callable) -> "Result[Any, E]":
        """Transform the value if success."""
        if self.success:
            return Result.ok(func(self.value))
        return Result.err(self.error)


# TypedDict for API responses

class ResourceResponse(TypedDict):
    """Standardized resource response."""
    id: str
    name: str
    type: str
    region: str | None
    status: str
    cost_per_month: float
    tags: dict[str, str]
    created_at: str
    updated_at: NotRequired[str]


class PaginatedResponse(TypedDict, Generic[T]):
    """Paginated response wrapper."""
    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool


class CostSummaryResponse(TypedDict):
    """Cost summary response."""
    this_month: float
    last_month: float
    forecast: float
    change_percent: float
    currency: str


class HealthCheckResponse(TypedDict):
    """Health check response."""
    status: str
    timestamp: str
    checks: list[dict[str, Any]]


# Cloud provider configuration types

class AWSConfig(TypedDict):
    """AWS configuration."""
    provider: str  # "aws"
    access_key_id: str
    secret_access_key: str
    region: str
    account_id: NotRequired[str]


class AzureConfig(TypedDict):
    """Azure configuration."""
    provider: str  # "azure"
    tenant_id: str
    client_id: str
    client_secret: str
    subscription_id: str


class GCPConfig(TypedDict):
    """GCP configuration."""
    provider: str  # "gcp"
    project_id: NotRequired[str]
    organization_id: NotRequired[str]
    credentials_json: str


CloudConfig = AWSConfig | AzureConfig | GCPConfig


# Filter and pagination types

class PaginationParams(TypedDict):
    """Pagination parameters."""
    page: int
    page_size: int


class SortParams(TypedDict):
    """Sorting parameters."""
    field: str
    order: str  # "asc" or "desc"


class DateRangeParams(TypedDict):
    """Date range parameters."""
    start_date: str  # ISO format
    end_date: str  # ISO format


# Event types

class AuditEventData(TypedDict):
    """Audit event data structure."""
    timestamp: str
    event_type: str
    user_id: NotRequired[str]
    organization_id: NotRequired[str]
    resource_type: NotRequired[str]
    resource_id: NotRequired[str]
    action_details: NotRequired[dict[str, Any]]
    success: bool
    severity: str


# Service result types

class ServiceResult(TypedDict):
    """Generic service operation result."""
    success: bool
    data: NotRequired[Any]
    error: NotRequired[str]
    error_code: NotRequired[str]
