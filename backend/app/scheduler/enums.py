"""Enums for scheduler module."""

from enum import Enum


class ScheduleType(str, Enum):
    """Types of schedule configurations."""
    INTERVAL = "interval"
    CRON = "cron"
    ONCE = "once"


class SchedulerStatus(str, Enum):
    """Status of a scheduler run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some data types succeeded, others failed


class LogLevel(str, Enum):
    """Log levels for scheduler logs."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TriggerType(str, Enum):
    """Type of trigger that started the scheduler."""
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    API = "api"
