"""Structured logging configuration with correlation IDs."""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

# Context variables for request-scoped data
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")
org_id_ctx: ContextVar[str] = ContextVar("org_id", default="")


class StructuredFormatter(logging.Formatter):
    """JSON structured logging formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get() or "",
            "user_id": user_id_ctx.get() or "",
            "org_id": org_id_ctx.get() or "",
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": self.formatException(record.exc_info),
            }

        # Add extra fields
        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "exc_info", "exc_text",
                "thread", "threadName", "taskName", "correlation_id",
                "user_id", "org_id",
            )
        }
        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str)


class RequestContextFilter(logging.Filter):
    """Add request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not correlation_id.get():
            record.correlation_id = ""
        else:
            record.correlation_id = correlation_id.get()
        record.user_id = user_id_ctx.get() or ""
        record.org_id = org_id_ctx.get() or ""
        return True


def setup_structured_logging(
    log_level: str = "INFO",
    use_json: bool = True,
) -> None:
    """Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Whether to use JSON structured logging
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    # Add context filter
    context_filter = RequestContextFilter()
    handler.addFilter(context_filter)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    logging.getLogger("google.api_core").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.info("Structured logging configured", extra={
        "log_level": log_level,
        "json_format": use_json,
    })
