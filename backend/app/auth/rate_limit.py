"""Simple in-memory rate limiter for auth endpoints."""

import time
from collections import defaultdict

from fastapi import Request
from app.shared.exceptions import TooManyRequestsError

# Track requests per IP: {ip: [(timestamp, ...), ...]}
_request_log: dict[str, list[float]] = defaultdict(list)

MAX_REQUESTS = 10  # per window
WINDOW_SECONDS = 60


async def auth_limiter(request: Request) -> None:
    """Dependency that rate-limits auth endpoints by client IP."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    log = _request_log[client_ip]

    # Prune expired entries
    _request_log[client_ip] = [t for t in log if now - t < WINDOW_SECONDS]
    log = _request_log[client_ip]

    if len(log) >= MAX_REQUESTS:
        raise TooManyRequestsError(
            "Too many requests. Please try again later.",
            retry_after_seconds=WINDOW_SECONDS,
        )

    log.append(now)
