"""Input validation middleware for security."""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import settings


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Validate and sanitize all incoming requests."""

    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "multipart/form-data",
        "text/plain",
        "application/x-www-form-urlencoded",
    }

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.max_request_size = getattr(settings, "MAX_REQUEST_SIZE_BYTES", 10 * 1024 * 1024)  # 10MB default

    def __getattr__(self, name):
        # Some unit tests monkeypatch __init__ and skip BaseHTTPMiddleware init.
        # Provide dispatch_func lazily so middleware remains callable.
        if name == "dispatch_func":
            return self.dispatch
        raise AttributeError(name)

    async def dispatch(self, request: Request, call_next):
        # 1. Request size validation
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request too large. Maximum size: {self.max_request_size} bytes"},
                    )
            except ValueError:
                    # Be tolerant of malformed headers and defer body parsing errors
                    # to downstream handlers instead of crashing middleware flow.
                    pass

        # 2. Content-Type validation for write operations
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()

            content_length_header = request.headers.get("content-length")
            body_present = False
            if content_length_header:
                try:
                    body_present = int(content_length_header) > 0
                except ValueError:
                    body_present = True

            if body_present and not content_type:
                raise HTTPException(status_code=415, detail="Unsupported media type: missing content type")
            if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail=f"Unsupported media type: {content_type}"
                )

        # 3. Path traversal prevention
        path = request.url.path
        scope = getattr(request, "scope", {}) or {}
        raw_path = scope.get("raw_path", b"")
        raw_path_text = raw_path.decode("utf-8", errors="ignore") if isinstance(raw_path, (bytes, bytearray)) else str(raw_path)
        if (
            ".." in path
            or "%2e%2e" in path.lower()
            or ".." in raw_path_text
            or "%2e%2e" in raw_path_text.lower()
        ):
            raise HTTPException(status_code=400, detail="Invalid path")

        # 4. Header validation - check for suspicious headers
        user_agent = request.headers.get("user-agent", "")
        if len(user_agent) > 1000:
            raise HTTPException(status_code=400, detail="User-Agent too long")

        response = await call_next(request)
        return response
