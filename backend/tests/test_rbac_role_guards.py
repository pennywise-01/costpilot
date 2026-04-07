import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.enterprise.modules.rbac.schemas import RoleCreate, RoleUpdate
from app.enterprise.modules.rbac.service import create_role, update_role, delete_role
from app.shared.exceptions import BadRequestError, ForbiddenError


class RbacRoleGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_role_rejects_system_role_name(self) -> None:
        db = AsyncMock()
        payload = RoleCreate(
            name="Organization Admin",
            description="",
            permissions=[],
            is_default=False,
        )

        with self.assertRaises(BadRequestError):
            await create_role(db, "org-1", payload)

        db.execute.assert_not_awaited()

    async def test_create_role_rejects_default_flag(self) -> None:
        db = AsyncMock()
        payload = RoleCreate(
            name="Custom Ops",
            description="",
            permissions=[],
            is_default=True,
        )

        with self.assertRaises(BadRequestError):
            await create_role(db, "org-1", payload)

        db.execute.assert_not_awaited()

    async def test_update_system_role_is_forbidden(self) -> None:
        db = AsyncMock()
        system_role = SimpleNamespace(is_default=True, permissions=[])

        with patch(
            "app.enterprise.modules.rbac.service.get_role",
            new=AsyncMock(return_value=system_role),
        ):
            with self.assertRaises(ForbiddenError):
                await update_role(db, "org-1", "role-1", RoleUpdate(description="x"))

        db.flush.assert_not_awaited()

    async def test_update_role_rejects_reserved_system_name(self) -> None:
        db = AsyncMock()
        custom_role = SimpleNamespace(is_default=False, permissions=[], name="Custom Role")

        with patch(
            "app.enterprise.modules.rbac.service.get_role",
            new=AsyncMock(return_value=custom_role),
        ):
            with self.assertRaises(BadRequestError):
                await update_role(db, "org-1", "role-1", RoleUpdate(name="Viewer"))

        db.flush.assert_not_awaited()

    async def test_delete_system_role_is_forbidden(self) -> None:
        db = AsyncMock()
        system_role = SimpleNamespace(is_default=True, permissions=[])

        with patch(
            "app.enterprise.modules.rbac.service.get_role",
            new=AsyncMock(return_value=system_role),
        ):
            with self.assertRaises(ForbiddenError):
                await delete_role(db, "org-1", "role-1")

        db.flush.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
