import secrets
import uuid
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.auth.models import User
from app.auth.service import revoke_session_binding
from app.database import async_session
from app.main import app


class SessionReplayProtectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.run_id = uuid.uuid4().hex[:10]
        self.email = f"session-replay-{self.run_id}@example.com"
        self.password = f"Cp!{secrets.token_urlsafe(12)}A1"
        self.display_name = "Session Replay Test"
        self.session_id: str | None = None

        self.client_primary = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"user-agent": "CostPilot-Primary-UA", "X-Forwarded-For": "192.168.1.100"},
        )

    async def asyncTearDown(self) -> None:
        await self.client_primary.aclose()

        if self.session_id:
            await revoke_session_binding(self.session_id)

        async with async_session() as db:
            await db.execute(delete(User).where(User.email == self.email))
            await db.commit()

    async def test_copied_token_and_session_blocked_in_different_context(self) -> None:
        # First, get a CSRF cookie (required for POST requests)
        csrf_resp = await self.client_primary.get("/health")
        csrf_token = self.client_primary.cookies.get("__Host-csrf-token")

        headers = {
            "user-agent": "CostPilot-Primary-UA",
            "X-Forwarded-For": "192.168.1.100",
        }
        if csrf_token:
            headers["x-csrf-token"] = csrf_token

        register = await self.client_primary.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "display_name": self.display_name,
                "password": self.password,
            },
            headers=headers,
        )
        self.assertEqual(register.status_code, 200, register.text)

        access_token = self.client_primary.cookies.get("access_token")
        session_id = self.client_primary.cookies.get("session_id")
        self.assertIsNotNone(access_token)
        self.assertIsNotNone(session_id)
        self.session_id = session_id

        me_primary = await self.client_primary.get("/api/v1/auth/me")
        self.assertEqual(me_primary.status_code, 200, me_primary.text)

        # Same context (same UA and IP) should work
        same_context = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"user-agent": "CostPilot-Primary-UA", "X-Forwarded-For": "192.168.1.100"},
        )
        try:
            same_context.cookies.set("access_token", access_token)
            same_context.cookies.set("session_id", session_id)
            me_same_context = await same_context.get("/api/v1/auth/me")
            self.assertEqual(me_same_context.status_code, 200, me_same_context.text)
        finally:
            await same_context.aclose()

        # Different UA should fail
        different_ua = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"user-agent": "CostPilot-Different-UA", "X-Forwarded-For": "192.168.1.100"},
        )
        try:
            different_ua.cookies.set("access_token", access_token)
            different_ua.cookies.set("session_id", session_id)
            me_different_ua = await different_ua.get("/api/v1/auth/me")
            self.assertEqual(me_different_ua.status_code, 401, me_different_ua.text)
        finally:
            await different_ua.aclose()

        # Different IP should fail (session replay from another location)
        different_ip = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"user-agent": "CostPilot-Primary-UA", "X-Forwarded-For": "10.0.0.50"},
        )
        try:
            different_ip.cookies.set("access_token", access_token)
            different_ip.cookies.set("session_id", session_id)
            me_different_ip = await different_ip.get("/api/v1/auth/me")
            self.assertEqual(me_different_ip.status_code, 401, me_different_ip.text)
        finally:
            await different_ip.aclose()


if __name__ == "__main__":
    unittest.main()
