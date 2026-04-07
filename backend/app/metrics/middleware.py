"""Middleware for collecting HTTP metrics."""
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.metrics.collector import record_request, HTTP_REQUESTS_IN_PROGRESS

class MetricsMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = ("/metrics", "/health", "/docs", "/redoc", "/openapi.json")
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)
        
        HTTP_REQUESTS_IN_PROGRESS.inc()
        start = time.time()
        
        try:
            response = await call_next(request)
            duration = time.time() - start
            record_request(request.method, request.url.path, response.status_code, duration)
            return response
        finally:
            HTTP_REQUESTS_IN_PROGRESS.dec()
