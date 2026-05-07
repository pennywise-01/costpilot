"""Wait for PostgreSQL to be reachable before running migrations.

Docker's depends_on + healthcheck doesn't guarantee DNS resolution is
propagated inside the container.  This script retries a TCP connection
to the database host extracted from DATABASE_URL so that alembic never
fails with ``socket.gaierror``.
"""

import asyncio
import os
import sys
import time
from urllib.parse import urlparse


def _get_host_port() -> tuple[str, int]:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        sys.exit(1)
    parsed = urlparse(url)
    return parsed.hostname or "localhost", parsed.port or 5432


async def _wait(host: str, port: int, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            print(f"Database {host}:{port} is reachable (attempt {attempt})")
            return
        except (OSError, ConnectionRefusedError) as exc:
            print(f"Waiting for database {host}:{port}... ({exc})")
            await asyncio.sleep(2)
    print(f"ERROR: Database {host}:{port} not reachable after {timeout}s", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    host, port = _get_host_port()
    asyncio.run(_wait(host, port))


if __name__ == "__main__":
    main()
