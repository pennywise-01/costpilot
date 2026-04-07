"""Enums for Data Export module."""

import enum


class ExportFormat(str, enum.Enum):
    """Supported export formats."""
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    PDF = "pdf"
    EXCEL = "excel"


class ExportDataType(str, enum.Enum):
    """Types of data that can be exported."""
    EXPENSES = "expenses"
    RESOURCES = "resources"
    RECOMMENDATIONS = "recommendations"
    CLOUD_ACCOUNTS = "cloud_accounts"
    POOLS = "pools"
    USERS = "users"
    ACTIVITY_LOGS = "activity_logs"
    SCHEDULER_RUNS = "scheduler_runs"


class ExportStatus(str, enum.Enum):
    """Export job lifecycle states."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class DeliveryMethod(str, enum.Enum):
    """Delivery methods for exported files."""
    DOWNLOAD = "download"  # Direct download from CostPilot
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    EMAIL = "email"
    SFTP = "sftp"


class ExportColumnType(str, enum.Enum):
    """Types of columns in export."""
    STRING = "string"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
