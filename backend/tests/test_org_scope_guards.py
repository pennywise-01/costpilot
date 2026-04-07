import unittest
from unittest.mock import AsyncMock, Mock

from app.enterprise.modules.export.service import get_export_job
from app.enterprise.modules.rbac.service import get_role
from app.recommendations.service import dismiss_recommendation


class _FakeCollection:
    def __init__(self, existing_item: dict | None = None) -> None:
        self._existing_item = existing_item
        self.find_query: dict | None = None
        self.update_query: dict | None = None
        self.update_doc: dict | None = None
        self.update_upsert: bool | None = None

    async def find_one(self, query: dict) -> dict | None:
        self.find_query = query
        return self._existing_item

    async def update_one(self, query: dict, update_doc: dict, upsert: bool = False) -> None:
        self.update_query = query
        self.update_doc = update_doc
        self.update_upsert = upsert


class _FakeMongoDb:
    def __init__(self, collection: _FakeCollection) -> None:
        self._collection = collection

    def __getitem__(self, _: str) -> _FakeCollection:
        return self._collection


class OrgScopedQueryTests(unittest.IsolatedAsyncioTestCase):
    async def _capture_statement(self, call) -> object:
        db = AsyncMock()
        execute_result = Mock()
        execute_result.scalar_one_or_none.return_value = object()
        db.execute.return_value = execute_result

        await call(db)

        db.execute.assert_awaited_once()
        return db.execute.await_args.args[0]

    def _assert_query_filters(self, stmt: object, expected_id: str, expected_org: str) -> None:
        where_criteria = list(stmt._where_criteria)
        value_by_column = {}

        for criterion in where_criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            if left is None or right is None:
                continue

            column_name = getattr(left, "key", None)
            value = getattr(right, "value", None)
            if column_name is not None:
                value_by_column[column_name] = value

        self.assertEqual(value_by_column.get("organization_id"), expected_org)
        self.assertEqual(value_by_column.get("id"), expected_id)

    async def test_get_export_job_query_includes_org_filter(self) -> None:
        stmt = await self._capture_statement(
            lambda db: get_export_job(db, "org-2", "job-2")
        )
        self._assert_query_filters(stmt, expected_id="job-2", expected_org="org-2")

    async def test_get_role_query_includes_org_filter(self) -> None:
        stmt = await self._capture_statement(
            lambda db: get_role(db, "org-3", "role-3")
        )
        self._assert_query_filters(stmt, expected_id="role-3", expected_org="org-3")

    async def test_dismiss_recommendation_update_is_org_scoped(self) -> None:
        fake_collection = _FakeCollection(existing_item={"dismissed": False})
        fake_mongo = _FakeMongoDb(fake_collection)

        result = await dismiss_recommendation(fake_mongo, "org-4", "rec-4")

        self.assertEqual(
            fake_collection.find_query,
            {"id": "rec-4", "organization_id": "org-4"},
        )
        self.assertEqual(
            fake_collection.update_query,
            {"id": "rec-4", "organization_id": "org-4"},
        )
        self.assertIsNotNone(fake_collection.update_doc)
        self.assertEqual(fake_collection.update_doc["$set"]["organization_id"], "org-4")
        self.assertTrue(fake_collection.update_upsert)
        self.assertEqual(result["id"], "rec-4")
        self.assertTrue(result["dismissed"])


if __name__ == "__main__":
    unittest.main()
