import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.database import async_session
from app.idempotency.models import IdempotencyKey
from sqlalchemy import select

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    EXEMPT_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS = ("/health", "/docs", "/redoc", "/openapi.json")
    HEADER_NAME = "idempotency-key"
    TTL_HOURS = 24

    def __init__(self, app, exclude_paths: list[str] | None = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or []

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in self.EXEMPT_METHODS:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in (*self.EXEMPT_PATHS, *self.exclude_paths)):
            return await call_next(request)

        idem_key = request.headers.get(self.HEADER_NAME)
        if not idem_key:
            return await call_next(request)

        # Hash the request body for matching
        body = await request.body()
        request_hash = hashlib.sha256(body).hexdigest()

        async with async_session() as db:
            # Check for existing key
            result = await db.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.key == idem_key,
                    IdempotencyKey.expires_at > datetime.now(timezone.utc),
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                if existing.request_hash == request_hash:
                    # Same request, return cached response
                    logger.info(f"Idempotency cache hit for key {idem_key}")
                    return Response(
                        content=existing.response_body,
                        status_code=existing.response_status,
                        media_type="application/json",
                        headers={"X-Idempotent": "true"},
                    )
                else:
                    # Different request body for same key
                    from app.shared.exceptions import ConflictError
                    raise ConflictError("Idempotency key already used with different request")

            # Store key for new request
            expires = datetime.now(timezone.utc) + timedelta(hours=self.TTL_HOURS)
            idem_record = IdempotencyKey(
                key=idem_key,
                user_id=getattr(request.state, "user_id", "anonymous"),
                endpoint=str(request.url.path),
                method=request.method,
                request_hash=request_hash,
                expires_at=expires,
            )
            db.add(idem_record)
            await db.flush()
            request.state.idempotency_record = idem_record

        response = await call_next(request)

        # Store response after successful execution
        if hasattr(request.state, "idempotency_record"):
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk
            try:
                body_str = body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_str = ""

            async with async_session() as db:
                record = await db.get(IdempotencyKey, request.state.idempotency_record.id)
                if record:
                    record.response_status = response.status_code
                    record.response_body = body_str
                    await db.flush()

            return Response(content=body_bytes, status_code=response.status_code, headers=dict(response.headers))

        return response
