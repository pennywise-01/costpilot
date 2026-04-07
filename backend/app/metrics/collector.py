"""Prometheus metrics collector."""
import logging
from prometheus_client import Counter, Histogram, Gauge, Enum

logger = logging.getLogger(__name__)

# HTTP metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed"
)

# Database metrics
DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active",
    "Active database connections"
)

DB_QUERIES_TOTAL = Counter(
    "db_queries_total",
    "Total database queries"
)

# Cache metrics
CACHE_HITS_TOTAL = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_name"]
)

CACHE_MISSES_TOTAL = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_name"]
)

# CSP API metrics
CSP_API_CALLS_TOTAL = Counter(
    "csp_api_calls_total",
    "Total CSP API calls",
    ["provider", "operation"]
)

CSP_API_ERRORS_TOTAL = Counter(
    "csp_api_errors_total",
    "Total CSP API errors",
    ["provider", "operation"]
)

CSP_API_LATENCY = Histogram(
    "csp_api_latency_seconds",
    "CSP API call latency in seconds",
    ["provider"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = Enum(
    "circuit_breaker_state",
    "Circuit breaker state",
    ["name"],
    states=["closed", "open", "half_open"]
)

# Scheduler metrics
SCHEDULER_RUNS_TOTAL = Counter(
    "scheduler_runs_total",
    "Total scheduler runs",
    ["config_id", "status"]
)

SCHEDULER_DURATION = Histogram(
    "scheduler_duration_seconds",
    "Scheduler run duration in seconds",
    ["config_id"]
)

# Export metrics
EXPORT_JOBS_TOTAL = Counter(
    "export_jobs_total",
    "Total export jobs",
    ["format", "status"]
)

# User metrics
ACTIVE_USERS = Gauge(
    "active_users",
    "Number of active users"
)

def record_request(method: str, endpoint: str, status: int, duration: float):
    """Record an HTTP request."""
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()
    HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

def record_cache_hit(cache_name: str, hit: bool):
    """Record a cache access."""
    if hit:
        CACHE_HITS_TOTAL.labels(cache_name=cache_name).inc()
    else:
        CACHE_MISSES_TOTAL.labels(cache_name=cache_name).inc()

def record_csp_call(provider: str, operation: str, success: bool, duration: float):
    """Record a CSP API call."""
    CSP_API_CALLS_TOTAL.labels(provider=provider, operation=operation).inc()
    CSP_API_LATENCY.labels(provider=provider).observe(duration)
    if not success:
        CSP_API_ERRORS_TOTAL.labels(provider=provider, operation=operation).inc()

def record_scheduler_run(config_id: str, status: str, duration: float):
    """Record a scheduler run."""
    SCHEDULER_RUNS_TOTAL.labels(config_id=config_id, status=status).inc()
    SCHEDULER_DURATION.labels(config_id=config_id).observe(duration)
