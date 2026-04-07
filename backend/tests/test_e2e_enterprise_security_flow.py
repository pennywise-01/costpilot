import uuid
import unittest

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.auth.models import User
from app.enterprise.modules.export.models import ExportJob, ExportTemplate
from app.enterprise.modules.rbac.models import (
    ABACPolicy,
    AccessReview,
    Role,
    RolePermission,
    SSOConfig,
    UserRoleAssignment,
)
from app.enterprise.modules.rbac.router import _require_rbac_admin, _require_rbac_view
from app.main import app
from app.database import async_session, engine, get_mongo_db
from app.organizations.models import Employee, Organization
from app.shared.enums import RolePurpose
from app.shared.org_access import get_current_org_member


class EnterpriseSecurityE2ETests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.run_id = uuid.uuid4().hex[:10]
        self.org_a = f"org-{self.run_id}-a"
        self.org_b = f"org-{self.run_id}-b"
        self.user_id = f"user-{self.run_id}"
        self.employee_id = f"emp-{self.run_id}"
        self.email = f"e2e-{self.run_id}@example.com"
        self.rec_id = f"rec-{self.run_id}"

        self.export_job_id: str | None = None
        self.export_template_id: str | None = None
        self.role_id: str | None = None
        self.assignment_id: str | None = None
        self.policy_id: str | None = None
        self.review_id: str | None = None
        self.sso_id: str | None = None

        async with async_session() as db:
            user = User(
                id=self.user_id,
                email=self.email,
                display_name="E2E User",
                hashed_password="not-used-in-e2e",
                is_active=True,
                verified=True,
            )
            org_one = Organization(
                id=self.org_a,
                name=f"e2e-org-{self.run_id}-a",
                currency="USD",
            )
            org_two = Organization(
                id=self.org_b,
                name=f"e2e-org-{self.run_id}-b",
                currency="USD",
            )
            employee = Employee(
                id=self.employee_id,
                name="E2E Employee",
                organization_id=self.org_a,
                auth_user_id=self.user_id,
                role=RolePurpose.MANAGER,
            )
            db.add_all([user, org_one, org_two, employee])
            await db.commit()

        member = Employee(
            id=self.employee_id,
            name="E2E Employee",
            organization_id=self.org_a,
            auth_user_id=self.user_id,
            role=RolePurpose.MANAGER,
        )

        async def override_org_member() -> Employee:
            return member

        async def override_rbac_gate() -> Employee:
            return member

        app.dependency_overrides[get_current_org_member] = override_org_member
        app.dependency_overrides[_require_rbac_view] = override_rbac_gate
        app.dependency_overrides[_require_rbac_admin] = override_rbac_gate

        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

        mongo = get_mongo_db()
        await mongo["recommendations"].delete_many(
            {
                "id": self.rec_id,
                "organization_id": {"$in": [self.org_a, self.org_b]},
            }
        )

        async with async_session() as db:
            if self.assignment_id:
                await db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.id == self.assignment_id))
            if self.review_id:
                await db.execute(delete(AccessReview).where(AccessReview.id == self.review_id))
            if self.policy_id:
                await db.execute(delete(ABACPolicy).where(ABACPolicy.id == self.policy_id))
            if self.sso_id:
                await db.execute(delete(SSOConfig).where(SSOConfig.id == self.sso_id))
            if self.role_id:
                await db.execute(delete(RolePermission).where(RolePermission.role_id == self.role_id))
                await db.execute(delete(Role).where(Role.id == self.role_id))
            if self.export_job_id:
                await db.execute(delete(ExportJob).where(ExportJob.id == self.export_job_id))
            if self.export_template_id:
                await db.execute(delete(ExportTemplate).where(ExportTemplate.id == self.export_template_id))

            await db.execute(delete(Employee).where(Employee.id == self.employee_id))
            await db.execute(delete(Organization).where(Organization.id.in_([self.org_a, self.org_b])))
            await db.execute(delete(User).where(User.id == self.user_id))
            await db.commit()

        await engine.dispose()

    def _assert_status(self, response, expected_status: int) -> None:
        self.assertEqual(
            response.status_code,
            expected_status,
            f"Expected {expected_status}, got {response.status_code}: {response.text}",
        )

    async def test_enterprise_flow_with_cross_org_guards(self) -> None:
        # Health + baseline security headers.
        health = await self.client.get("/api/v1/health")
        self._assert_status(health, 200)
        self.assertEqual(health.json().get("status"), "healthy")
        self.assertEqual(health.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(health.headers.get("x-frame-options"), "DENY")
        self.assertEqual(health.headers.get("referrer-policy"), "no-referrer")

        # Export template + export execution + file download + org scoping.
        create_template = await self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_a}/export-templates",
            json={
                "name": f"e2e-template-{self.run_id}",
                "description": "E2E export template",
                "data_type": "expenses",
                "format": "csv",
                "columns": [],
                "filters": {},
                "sort_order": "desc",
                "is_public": False,
            },
        )
        self._assert_status(create_template, 201)
        template_id = create_template.json()["id"]
        self.export_template_id = template_id

        get_template_other_org = await self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_b}/export-templates/{template_id}"
        )
        self._assert_status(get_template_other_org, 404)

        create_export = await self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_a}/exports",
            json={
                "name": f"e2e-export-{self.run_id}",
                "template_id": template_id,
                "data_type": "expenses",
                "format": "csv",
                "columns": [],
                "filters": {},
                "sort_order": "desc",
            },
        )
        self._assert_status(create_export, 201)
        self.export_job_id = create_export.json()["id"]

        execute_export = await self.client.post(
            f"/api/v1/enterprise/organizations/{self.org_a}/exports/{self.export_job_id}/execute"
        )
        self._assert_status(execute_export, 200)
        execute_body = execute_export.json()
        self.assertEqual(execute_body["status"], "completed", execute_body.get("error_message"))
        self.assertFalse(execute_body.get("error_message"))

        get_export_other_org = await self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_b}/exports/{self.export_job_id}"
        )
        self._assert_status(get_export_other_org, 404)

        download_info = await self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_a}/exports/{self.export_job_id}/download"
        )
        self._assert_status(download_info, 200)

        export_file = await self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_a}/exports/{self.export_job_id}/file"
        )
        self._assert_status(export_file, 200)

        get_export = await self.client.get(
            f"/api/v1/enterprise/organizations/{self.org_a}/exports/{self.export_job_id}"
        )
        self._assert_status(get_export, 200)

        # RBAC lifecycle + org scoping.
        create_role = await self.client.post(
            f"/api/v1/enterprise/{self.org_a}/rbac/roles",
            json={
                "name": f"e2e-role-{self.run_id}",
                "description": "E2E role",
                "permissions": [
                    {"action": "manage", "resource_type": "user"},
                    {"action": "manage", "resource_type": "recommendation"},
                ],
                "is_default": False,
            },
        )
        self._assert_status(create_role, 201)
        self.role_id = create_role.json()["id"]

        get_role_other_org = await self.client.get(
            f"/api/v1/enterprise/{self.org_b}/rbac/roles/{self.role_id}"
        )
        self._assert_status(get_role_other_org, 404)

        assign_role = await self.client.post(
            f"/api/v1/enterprise/{self.org_a}/rbac/assignments",
            json={"user_id": self.user_id, "role_id": self.role_id},
        )
        self._assert_status(assign_role, 201)
        self.assignment_id = assign_role.json()["id"]

        check_permission = await self.client.post(
            f"/api/v1/enterprise/{self.org_a}/rbac/check",
            json={
                "user_id": self.user_id,
                "action": "read",
                "resource_type": "user",
                "resource_attributes": {},
            },
        )
        self._assert_status(check_permission, 200)
        self.assertTrue(check_permission.json().get("allowed"))

        create_policy = await self.client.post(
            f"/api/v1/enterprise/{self.org_a}/rbac/policies",
            json={
                "name": f"e2e-policy-{self.run_id}",
                "description": "policy",
                "resource_type": "user",
                "action": "read",
                "attribute_key": "department",
                "operator": "equals",
                "attribute_value": "finance",
                "effect_allow": True,
                "active": True,
            },
        )
        self._assert_status(create_policy, 201)
        self.policy_id = create_policy.json()["id"]

        create_review = await self.client.post(
            f"/api/v1/enterprise/{self.org_a}/rbac/reviews",
            json={"user_id": self.user_id, "role_id": self.role_id, "notes": "e2e"},
        )
        self._assert_status(create_review, 201)
        self.review_id = create_review.json()["id"]

        decide_review = await self.client.patch(
            f"/api/v1/enterprise/{self.org_a}/rbac/reviews/{self.review_id}",
            json={"status": "approved", "notes": "approved in e2e"},
        )
        self._assert_status(decide_review, 200)

        create_sso = await self.client.post(
            f"/api/v1/enterprise/{self.org_a}/rbac/sso",
            json={
                "provider": "oidc",
                "issuer_url": "https://issuer.example.com",
                "client_id": "client-e2e",
                "metadata_url": "https://issuer.example.com/.well-known/openid-configuration",
                "enabled": False,
                "auto_provision_roles": False,
                "default_role_id": self.role_id,
            },
        )
        self._assert_status(create_sso, 201)
        self.sso_id = create_sso.json()["id"]

        # Recommendation dismiss org-isolation behavior.
        dismiss_org_a = await self.client.patch(
            f"/api/v1/organizations/{self.org_a}/recommendations/{self.rec_id}/dismiss"
        )
        self._assert_status(dismiss_org_a, 200)
        self.assertTrue(dismiss_org_a.json().get("dismissed"))

        dismiss_org_b = await self.client.patch(
            f"/api/v1/organizations/{self.org_b}/recommendations/{self.rec_id}/dismiss"
        )
        self._assert_status(dismiss_org_b, 403)

        # Delete paths should complete successfully without datetime coercion errors.
        delete_sso = await self.client.delete(
            f"/api/v1/enterprise/{self.org_a}/rbac/sso/{self.sso_id}"
        )
        self._assert_status(delete_sso, 200)

        revoke_assignment = await self.client.delete(
            f"/api/v1/enterprise/{self.org_a}/rbac/assignments/{self.assignment_id}"
        )
        self._assert_status(revoke_assignment, 200)

        delete_policy = await self.client.delete(
            f"/api/v1/enterprise/{self.org_a}/rbac/policies/{self.policy_id}"
        )
        self._assert_status(delete_policy, 200)

        delete_role = await self.client.delete(
            f"/api/v1/enterprise/{self.org_a}/rbac/roles/{self.role_id}"
        )
        self._assert_status(delete_role, 200)

if __name__ == "__main__":
    unittest.main()
