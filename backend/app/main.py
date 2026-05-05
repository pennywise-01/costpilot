import secrets
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings
from app.database import engine, close_mongo_client
from app.shared.logging_config import (
    correlation_id,
    org_id_ctx,
    setup_structured_logging,
    user_id_ctx,
)
from app.shared.feature_flags import init_feature_flags
from app.shared.feature_flags_router import router as feature_flags_router

# Configure structured logging before app creation
setup_structured_logging(
    log_level="DEBUG" if settings.DEBUG else "INFO",
    use_json=True,
)
from app.auth.router import router as auth_router
from app.auth.service import _get_redis, close_redis_client
from app.middleware import (
    InputValidationMiddleware,
    RateLimitMiddleware,
    TimeoutMiddleware,
)
from app.middleware.exception_handler import GlobalExceptionHandler
from app.middleware.idempotency import IdempotencyMiddleware
from app.metrics.middleware import MetricsMiddleware
from app.metrics.router import router as metrics_router
from app.health import health_registry
from app.organizations.router import router as organizations_router
from app.cloud_accounts.router import router as cloud_accounts_router
from app.pools.router import router as pools_router
from app.expenses.router import router as expenses_router
from app.resources.router import router as resources_router
from app.recommendations.router import router as recommendations_router
from app.rules.router import router as rules_router
from app.recommendation_rules.router import router as rec_rules_router
from app.enterprise.router import router as enterprise_router
from app.enterprise.modules.rbac.router import router as rbac_router
from app.notifications.router import router as notifications_router
from app.scheduler.router import router as scheduler_router
from app.scheduler.executor import init_scheduler, load_schedulers_from_db, shutdown_scheduler
from app.user_management.router import router as user_management_router
from app.enterprise.modules.export.router import router as export_router
from app.dashboards.router import router as dashboards_router
from app.advisor_findings.router import router as advisor_findings_router
from app.config_ingestors.router import router as config_snapshots_router

# Import all models so Base.metadata knows about them (single registry)
import app.models_registry  # noqa: F401


class CorrelationIdMiddleware:
    """Generate and propagate correlation IDs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        correlation = headers.get(b"x-correlation-id", b"").decode()
        if not correlation:
            correlation = str(uuid.uuid4())

        # Set context var for this request
        correlation_id.set(correlation)

        # Add to response headers
        async def send_with_correlation(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_correlation)


class HealthEndpointMiddleware(BaseHTTPMiddleware):
    """Restrict /health/detailed to local/internal IPs."""
    ALLOWED_IPS = {"127.0.0.1", "::1", "localhost"}

    async def dispatch(self, request, call_next):
        if request.url.path == "/health/detailed":
            client_ip = request.client.host if request.client else ""
            forwarded_for = request.headers.get("x-forwarded-for", "")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()

            if client_ip not in self.ALLOWED_IPS:
                from app.shared.exceptions import ForbiddenError
                raise ForbiddenError("Detailed health check is restricted to internal IPs")

        return await call_next(request)


def set_request_context(user_id: str = "", org_id: str = "") -> None:
    """Set user_id and org_id context from the authenticated user."""
    if user_id:
        user_id_ctx.set(user_id)
    if org_id:
        org_id_ctx.set(org_id)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF pattern.

    Exempts API endpoints (/api/v1/*) since:
    - SameSite=strict cookies already protect against CSRF
    - API clients (mobile, CLI, scripts) don't use browser cookies
    - Frontend uses httpOnly cookies with SameSite=strict
    """

    EXEMPT_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS = ("/api/v1/", "/health", "/docs", "/redoc", "/openapi.json")
    CSRF_COOKIE_NAME = "__Host-csrf-token"
    CSRF_HEADER_NAME = "x-csrf-token"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Exempt safe methods
        if request.method in self.EXEMPT_METHODS:
            response = await call_next(request)
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                key=self.CSRF_COOKIE_NAME,
                value=token,
                httponly=False,
                secure=True,
                samesite="strict",
                path="/",
            )
            return response

        # Exempt API endpoints (SameSite=strict provides CSRF protection for cookies)
        if any(request.url.path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)

        # Validate CSRF token for state-changing non-API requests
        cookie_token = request.cookies.get(self.CSRF_COOKIE_NAME, "")
        header_token = request.headers.get(self.CSRF_HEADER_NAME, "")

        if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
            from app.shared.exceptions import ForbiddenError
            raise ForbiddenError("Invalid or missing CSRF token")

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database schema is managed via Alembic migrations.
    # See docker-compose backend command: "alembic upgrade head" before app startup.
    
    # Initialize OpenTelemetry tracing
    from app.shared.tracing import init_tracing
    init_tracing()
    
    # Initialize feature flags
    init_feature_flags()
    
    # Initialize and start the scheduler
    init_scheduler()
    await load_schedulers_from_db()
    
    # Store Redis client in app state for middleware
    app.state.redis = await _get_redis()
    
    yield
    
    # Shutdown the scheduler
    shutdown_scheduler()
    await engine.dispose()
    await close_mongo_client()
    await close_redis_client()


app = FastAPI(
    title=settings.APP_NAME,
    description="Cloud Cost Optimization Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Instrument FastAPI with OpenTelemetry (no-op if OTEL_ENABLED=False)
from app.shared.tracing import instrument_fastapi_app
instrument_fastapi_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Add CSRF middleware after CORSMiddleware
app.add_middleware(CSRFMiddleware)

# Add health endpoint restriction middleware early in the chain
app.add_middleware(HealthEndpointMiddleware)

# Add metrics middleware after CSRF middleware
app.add_middleware(MetricsMiddleware)

# Add GZip compression for responses over 1000 bytes
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add middleware (applied in reverse order)
# Correlation ID should be first to set context for all subsequent middleware
app.add_middleware(CorrelationIdMiddleware)
# Exception handler should be first to catch all errors
app.add_middleware(GlobalExceptionHandler)
# Idempotency middleware for write operations
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(TimeoutMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(InputValidationMiddleware)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' http://localhost:8000 https://*; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    is_https = request.url.scheme == "https" or forwarded_proto.split(",")[0].strip().lower() == "https"
    if is_https:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    return response


app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(organizations_router, prefix="/api/v1/organizations", tags=["Organizations"])
app.include_router(cloud_accounts_router, prefix="/api/v1", tags=["Cloud Accounts"])
app.include_router(pools_router, prefix="/api/v1", tags=["Pools"])
app.include_router(expenses_router, prefix="/api/v1", tags=["Expenses"])
app.include_router(resources_router, prefix="/api/v1", tags=["Resources"])
app.include_router(recommendations_router, prefix="/api/v1", tags=["Recommendations"])
app.include_router(rules_router, prefix="/api/v1", tags=["Rules"])
app.include_router(rec_rules_router, prefix="/api/v1", tags=["Recommendation Rules"])
app.include_router(enterprise_router, prefix="/api/v1/enterprise", tags=["Enterprise"])
app.include_router(rbac_router, prefix="/api/v1/enterprise", tags=["Advanced RBAC"])
app.include_router(notifications_router, prefix="/api/v1", tags=["Notifications"])
app.include_router(scheduler_router, prefix="/api/v1", tags=["Scheduler"])
app.include_router(user_management_router, prefix="/api/v1", tags=["User Management"])
app.include_router(export_router, prefix="/api/v1/enterprise", tags=["Data Export"])
app.include_router(dashboards_router, prefix="/api/v1", tags=["Dashboards"])
app.include_router(advisor_findings_router, prefix="/api/v1", tags=["Advisor Findings"])
app.include_router(config_snapshots_router, prefix="/api/v1", tags=["Config Snapshots"])
app.include_router(feature_flags_router, prefix="/api/v1", tags=["Feature Flags"])

# Metrics router (no prefix - /metrics at root)
app.include_router(metrics_router)


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "app": settings.APP_NAME}


@app.get("/health/detailed")
async def health_check_detailed():
    """Detailed health check with all dependencies."""
    return await health_registry.run_all()


@app.get("/api/v1/health")
async def api_health_check():
    """API health check for backward compatibility."""
    return {"status": "healthy", "app": settings.APP_NAME}
