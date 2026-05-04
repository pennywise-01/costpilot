"""OpenTelemetry distributed tracing configuration.

Provides request-level tracing across the full stack:
middleware → router → service → cloud adapter → external API.

When OTEL_ENABLED is False (default), all tracing is no-op — zero overhead.
"""

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded globals — only imported when tracing is enabled
_tracer = None
_initialized = False


def _get_tracer():
    """Return the application tracer (lazy singleton)."""
    global _tracer
    if _tracer is None:
        from opentelemetry import trace
        _tracer = trace.get_tracer("costpilot", settings.APP_VERSION if hasattr(settings, "APP_VERSION") else "0.1.0")
    return _tracer


def init_tracing() -> None:
    """Initialize OpenTelemetry tracing pipeline.

    Call once during application startup (in lifespan).
    Safe to call multiple times — only initializes once.
    """
    global _initialized
    if _initialized:
        return

    if not getattr(settings, "OTEL_ENABLED", False):
        logger.info("OpenTelemetry tracing disabled (OTEL_ENABLED=False)")
        _initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        # Build resource with service identity
        resource = Resource.create({
            SERVICE_NAME: "costpilot-backend",
            "service.version": getattr(settings, "APP_VERSION", "0.1.0"),
            "deployment.environment": "production" if not settings.DEBUG else "development",
        })

        provider = TracerProvider(resource=resource)

        # Configure exporter — OTLP gRPC if endpoint set, otherwise console for dev
        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "")
        if otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            logger.info("OpenTelemetry OTLP exporter configured: %s", otlp_endpoint)
        else:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            exporter = ConsoleSpanExporter()
            logger.info("OpenTelemetry console exporter (no OTEL_EXPORTER_OTLP_ENDPOINT set)")

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Instrument FastAPI
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        # Will be called with app instance in main.py

        # Instrument SQLAlchemy
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument(enable_commenter=True)
        except Exception as e:
            logger.debug("SQLAlchemy instrumentation skipped: %s", e)

        # Instrument Redis
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            RedisInstrumentor().instrument()
        except Exception as e:
            logger.debug("Redis instrumentation skipped: %s", e)

        # Instrument httpx (used by Azure/GCP SDKs)
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
        except Exception as e:
            logger.debug("httpx instrumentation skipped: %s", e)

        _initialized = True
        logger.info("OpenTelemetry tracing initialized successfully")

    except ImportError as e:
        logger.warning("OpenTelemetry packages not installed, tracing disabled: %s", e)
        _initialized = True
    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry tracing: %s", e)
        _initialized = True


def instrument_fastapi_app(app) -> None:
    """Instrument a FastAPI app with OpenTelemetry.

    Call after creating the FastAPI app instance.
    """
    if not getattr(settings, "OTEL_ENABLED", False):
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.warning("Failed to instrument FastAPI with OpenTelemetry: %s", e)


def get_current_span():
    """Get the current active span (or None if tracing disabled)."""
    if not getattr(settings, "OTEL_ENABLED", False):
        return None
    try:
        from opentelemetry import trace
        return trace.get_current_span()
    except Exception:
        return None


def add_span_attributes(attributes: dict) -> None:
    """Add attributes to the current span.

    No-op if tracing is disabled or no active span.
    """
    span = get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, str(value))


def add_span_event(name: str, attributes: Optional[dict] = None) -> None:
    """Add a timed event to the current span.

    No-op if tracing is disabled or no active span.
    """
    span = get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span.

    No-op if tracing is disabled or no active span.
    """
    span = get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(
            status_code=2,  # ERROR
            description=str(exception)[:200],
        )


def create_span(name: str, attributes: Optional[dict] = None):
    """Create a new child span as a context manager.

    Usage:
        async with create_span("fetch_costs", {"provider": "aws"}):
            result = await adapter.get_monthly_cost_summary()

    Returns a no-op context manager if tracing is disabled.
    """
    if not getattr(settings, "OTEL_ENABLED", False):
        return _NoOpSpan()

    tracer = _get_tracer()
    return tracer.start_as_current_span(name, attributes=attributes)


class _NoOpSpan:
    """No-op context manager for when tracing is disabled."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
