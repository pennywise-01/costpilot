"""Simple rate limiting using in-memory sliding window."""

import time
from collections import defaultdict

from app.shared.exceptions import BadRequestError

_windows: dict[str, list[float]] = defaultdict(list)


async def check_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> None:
    """Check if a request is within rate limits.

    Uses an in-memory sliding window. For distributed deployments,
    replace with a Redis-backed implementation.

    Raises BadRequestError if rate limit is exceeded.
    """
    now = time.time()
    cutoff = now - window_seconds

    # Remove expired entries
    _windows[key] = [ts for ts in _windows[key] if ts > cutoff]

    if len(_windows[key]) >= max_requests:
        raise BadRequestError(
            f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s. "
            "Please wait before retrying."
        )

    _windows[key].append(now)
