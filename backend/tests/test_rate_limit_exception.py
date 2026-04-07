import unittest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.auth.rate_limit import WINDOW_SECONDS
from app.middleware.exception_handler import GlobalExceptionHandler
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.timeout import TimeoutMiddleware
from app.middleware.validation import InputValidationMiddleware
from app.shared.exceptions import TooManyRequestsError


class RateLimitExceptionTests(unittest.TestCase):
    def test_too_many_requests_status_and_retry_after(self) -> None:
        exc = TooManyRequestsError(
            "Too many requests. Please try again later.",
            retry_after_seconds=WINDOW_SECONDS,
        )
        self.assertEqual(exc.status_code, 429)
        self.assertEqual(exc.headers.get("Retry-After"), str(WINDOW_SECONDS))

    def test_export_write_rate_limit_surfaces_as_429(self) -> None:
        app = FastAPI()
        app.add_middleware(GlobalExceptionHandler)
        app.add_middleware(TimeoutMiddleware)
        app.add_middleware(RateLimitMiddleware)
        app.add_middleware(InputValidationMiddleware)

        @app.middleware("http")
        async def passthrough_security_headers(request: Request, call_next):
            return await call_next(request)

        @app.post("/api/v1/export")
        async def export_endpoint():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        status_codes = [client.post("/api/v1/export").status_code for _ in range(6)]

        self.assertEqual(status_codes[:5], [200, 200, 200, 200, 200])
        self.assertEqual(status_codes[5], 429)

    def test_export_reads_do_not_block_export_writes(self) -> None:
        app = FastAPI()
        app.add_middleware(GlobalExceptionHandler)
        app.add_middleware(TimeoutMiddleware)
        app.add_middleware(RateLimitMiddleware)
        app.add_middleware(InputValidationMiddleware)

        @app.middleware("http")
        async def passthrough_security_headers(request: Request, call_next):
            return await call_next(request)

        endpoint = "/api/v1/enterprise/organizations/org-1/exports"

        @app.get(endpoint)
        async def list_exports():
            return {"items": []}

        @app.post(endpoint)
        async def create_export():
            return {"id": "job-1"}

        client = TestClient(app, raise_server_exceptions=False)

        read_statuses = [client.get(endpoint).status_code for _ in range(10)]
        create_status = client.post(endpoint).status_code

        self.assertTrue(all(code == 200 for code in read_statuses))
        self.assertEqual(create_status, 200)

    def test_session_scoped_export_limits_do_not_collide(self) -> None:
        app = FastAPI()
        app.add_middleware(GlobalExceptionHandler)
        app.add_middleware(TimeoutMiddleware)
        app.add_middleware(RateLimitMiddleware)
        app.add_middleware(InputValidationMiddleware)

        @app.middleware("http")
        async def passthrough_security_headers(request: Request, call_next):
            return await call_next(request)

        @app.post("/api/v1/export")
        async def export_endpoint():
            return {"ok": True}

        client_a = TestClient(app, raise_server_exceptions=False)
        client_b = TestClient(app, raise_server_exceptions=False)

        client_a.cookies.set("session_id", "session-a")
        client_b.cookies.set("session_id", "session-b")

        for _ in range(5):
            self.assertEqual(client_a.post("/api/v1/export").status_code, 200)

        self.assertEqual(client_a.post("/api/v1/export").status_code, 429)
        self.assertEqual(client_b.post("/api/v1/export").status_code, 200)


if __name__ == "__main__":
    unittest.main()
