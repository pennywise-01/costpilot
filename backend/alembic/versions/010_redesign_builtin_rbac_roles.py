"""Redesign built-in RBAC roles

Revision ID: 010
Revises: 009
Create Date: 2026-04-06 13:30:00.000000

"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE_SPECS = [
    {
        "name": "Organization Admin",
        "description": "Full administrative control across all organization resources.",
        "permissions": [
            ("manage", "organization"),
            ("manage", "user"),
            ("manage", "cloud_account"),
            ("manage", "pool"),
            ("manage", "expense"),
            ("manage", "resource"),
            ("manage", "recommendation"),
            ("manage", "rule"),
            ("manage", "notification"),
            ("manage", "enterprise"),
        ],
    },
    {
        "name": "Admin View Only",
        "description": "Read-only visibility across organization and enterprise resources.",
        "permissions": [
            ("read", "organization"),
            ("read", "user"),
            ("read", "cloud_account"),
            ("read", "pool"),
            ("read", "expense"),
            ("read", "resource"),
            ("read", "recommendation"),
            ("read", "rule"),
            ("read", "notification"),
            ("read", "enterprise"),
        ],
    },
    {
        "name": "Engineer",
        "description": "Operational role for engineering workflows with limited write access.",
        "permissions": [
            ("read", "organization"),
            ("read", "user"),
            ("read", "cloud_account"),
            ("create", "cloud_account"),
            ("update", "cloud_account"),
            ("read", "pool"),
            ("read", "expense"),
            ("read", "resource"),
            ("manage", "recommendation"),
            ("read", "rule"),
            ("read", "notification"),
        ],
    },
    {
        "name": "Viewer",
        "description": "General read-only access for business stakeholders.",
        "permissions": [
            ("read", "organization"),
            ("read", "user"),
            ("read", "cloud_account"),
            ("read", "pool"),
            ("read", "expense"),
            ("read", "resource"),
            ("read", "recommendation"),
            ("read", "rule"),
            ("read", "notification"),
            ("read", "enterprise"),
        ],
    },
    {
        "name": "Billing Admin",
        "description": "Cost and billing operations role with expense management access.",
        "permissions": [
            ("read", "organization"),
            ("read", "user"),
            ("read", "cloud_account"),
            ("read", "pool"),
            ("manage", "expense"),
            ("read", "resource"),
            ("read", "recommendation"),
            ("read", "notification"),
            ("read", "enterprise"),
        ],
    },
    {
        "name": "Security Auditor",
        "description": "Read-only role for security and compliance review workflows.",
        "permissions": [
            ("read", "organization"),
            ("read", "user"),
            ("read", "cloud_account"),
            ("read", "pool"),
            ("read", "expense"),
            ("read", "resource"),
            ("read", "recommendation"),
            ("read", "rule"),
            ("read", "notification"),
            ("read", "enterprise"),
        ],
    },
]

LEGACY_ROLE_RENAMES = {
    "Organization Owner": "Organization Admin",
    "Finance": "Billing Admin",
}


def _fetch_role(bind, org_id: str, role_name: str):
    return bind.execute(
        sa.text(
            """
            SELECT id, deleted_at
            FROM rbac_roles
            WHERE organization_id = :org_id
              AND name = :role_name
            ORDER BY
              CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END,
              created_at
            LIMIT 1
            """
        ),
        {"org_id": org_id, "role_name": role_name},
    ).mappings().first()


def _sync_role_permissions(bind, role_id: str, desired_permissions: list[tuple[str, str]], now: datetime) -> None:
    desired_set = {
        (action.upper(), resource_type.upper())
        for action, resource_type in desired_permissions
    }
    permission_rows = bind.execute(
        sa.text(
            """
            SELECT id, action, resource_type, deleted_at
            FROM rbac_role_permissions
            WHERE role_id = :role_id
            """
        ),
        {"role_id": role_id},
    ).mappings().all()

    existing_by_key = {
        (row["action"], row["resource_type"]): row
        for row in permission_rows
    }

    for key, row in existing_by_key.items():
        if key in desired_set:
            if row["deleted_at"] is not None:
                bind.execute(
                    sa.text(
                        """
                        UPDATE rbac_role_permissions
                        SET deleted_at = NULL,
                            updated_at = :now
                        WHERE id = :permission_id
                        """
                    ),
                    {"permission_id": row["id"], "now": now},
                )
            continue

        if row["deleted_at"] is None:
            bind.execute(
                sa.text(
                    """
                    UPDATE rbac_role_permissions
                    SET deleted_at = :now,
                        updated_at = :now
                    WHERE id = :permission_id
                    """
                ),
                {"permission_id": row["id"], "now": now},
            )

    for action, resource_type in desired_set:
        existing = existing_by_key.get((action, resource_type))
        if existing:
            continue

        bind.execute(
            sa.text(
                """
                INSERT INTO rbac_role_permissions (
                    id,
                    created_at,
                    updated_at,
                    deleted_at,
                    role_id,
                    action,
                    resource_type
                ) VALUES (
                    :id,
                    :now,
                    :now,
                    NULL,
                    :role_id,
                    :action,
                    :resource_type
                )
                """
            ),
            {
                "id": str(uuid4()),
                "now": now,
                "role_id": role_id,
                "action": action,
                "resource_type": resource_type,
            },
        )


def _upsert_system_role(bind, org_id: str, role_spec: dict, now: datetime) -> str:
    role_name = role_spec["name"]
    role_row = _fetch_role(bind, org_id, role_name)

    if role_row:
        role_id = role_row["id"]
        bind.execute(
            sa.text(
                """
                UPDATE rbac_roles
                SET description = :description,
                    is_default = true,
                    deleted_at = NULL,
                    updated_at = :now
                WHERE id = :role_id
                """
            ),
            {
                "role_id": role_id,
                "description": role_spec["description"],
                "now": now,
            },
        )
    else:
        role_id = str(uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO rbac_roles (
                    id,
                    created_at,
                    updated_at,
                    deleted_at,
                    name,
                    description,
                    organization_id,
                    is_default
                ) VALUES (
                    :id,
                    :now,
                    :now,
                    NULL,
                    :name,
                    :description,
                    :org_id,
                    true
                )
                """
            ),
            {
                "id": role_id,
                "now": now,
                "name": role_name,
                "description": role_spec["description"],
                "org_id": org_id,
            },
        )

    _sync_role_permissions(bind, role_id, role_spec["permissions"], now)
    return role_id


def _migrate_assignments(bind, org_id: str, old_role_id: str, new_role_id: str, now: datetime) -> None:
    assignment_rows = bind.execute(
        sa.text(
            """
            SELECT id, user_id, assigned_by, assigned_at, expires_at
            FROM rbac_user_roles
            WHERE organization_id = :org_id
              AND role_id = :old_role_id
              AND deleted_at IS NULL
            """
        ),
        {"org_id": org_id, "old_role_id": old_role_id},
    ).mappings().all()

    for assignment in assignment_rows:
        existing = bind.execute(
            sa.text(
                """
                SELECT id, deleted_at
                FROM rbac_user_roles
                WHERE organization_id = :org_id
                  AND user_id = :user_id
                  AND role_id = :new_role_id
                ORDER BY CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END
                LIMIT 1
                """
            ),
            {
                "org_id": org_id,
                "user_id": assignment["user_id"],
                "new_role_id": new_role_id,
            },
        ).mappings().first()

        if existing:
            if existing["deleted_at"] is not None:
                bind.execute(
                    sa.text(
                        """
                        UPDATE rbac_user_roles
                        SET deleted_at = NULL,
                            assigned_by = :assigned_by,
                            assigned_at = :assigned_at,
                            expires_at = :expires_at,
                            updated_at = :now
                        WHERE id = :assignment_id
                        """
                    ),
                    {
                        "assignment_id": existing["id"],
                        "assigned_by": assignment["assigned_by"],
                        "assigned_at": assignment["assigned_at"],
                        "expires_at": assignment["expires_at"],
                        "now": now,
                    },
                )
        else:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO rbac_user_roles (
                        id,
                        created_at,
                        updated_at,
                        deleted_at,
                        user_id,
                        role_id,
                        organization_id,
                        assigned_by,
                        assigned_at,
                        expires_at
                    ) VALUES (
                        :id,
                        :now,
                        :now,
                        NULL,
                        :user_id,
                        :role_id,
                        :org_id,
                        :assigned_by,
                        :assigned_at,
                        :expires_at
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "now": now,
                    "user_id": assignment["user_id"],
                    "role_id": new_role_id,
                    "org_id": org_id,
                    "assigned_by": assignment["assigned_by"],
                    "assigned_at": assignment["assigned_at"],
                    "expires_at": assignment["expires_at"],
                },
            )

    bind.execute(
        sa.text(
            """
            UPDATE rbac_user_roles
            SET deleted_at = :now,
                updated_at = :now
            WHERE organization_id = :org_id
              AND role_id = :old_role_id
              AND deleted_at IS NULL
            """
        ),
        {"now": now, "org_id": org_id, "old_role_id": old_role_id},
    )


def _soft_delete_role(bind, role_id: str, now: datetime) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE rbac_role_permissions
            SET deleted_at = :now,
                updated_at = :now
            WHERE role_id = :role_id
              AND deleted_at IS NULL
            """
        ),
        {"role_id": role_id, "now": now},
    )

    bind.execute(
        sa.text(
            """
            UPDATE rbac_roles
            SET deleted_at = :now,
                updated_at = :now
            WHERE id = :role_id
              AND deleted_at IS NULL
            """
        ),
        {"role_id": role_id, "now": now},
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    required_tables = {
        "organizations",
        "rbac_roles",
        "rbac_role_permissions",
        "rbac_user_roles",
    }
    for table_name in required_tables:
        if not inspector.has_table(table_name):
            return

    org_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM organizations WHERE deleted_at IS NULL")
        ).fetchall()
    ]

    for org_id in org_ids:
        now = datetime.now(timezone.utc)
        role_ids_by_name = {}

        for role_spec in ROLE_SPECS:
            role_id = _upsert_system_role(bind, org_id, role_spec, now)
            role_ids_by_name[role_spec["name"]] = role_id

        for legacy_name, target_name in LEGACY_ROLE_RENAMES.items():
            legacy_role = _fetch_role(bind, org_id, legacy_name)
            if not legacy_role or legacy_role["deleted_at"] is not None:
                continue

            target_role_id = role_ids_by_name[target_name]
            if legacy_role["id"] == target_role_id:
                continue

            _migrate_assignments(bind, org_id, legacy_role["id"], target_role_id, now)
            _soft_delete_role(bind, legacy_role["id"], now)


def downgrade() -> None:
    # Data migration is intentionally non-destructive on downgrade.
    # Legacy role names/assignments are not restored automatically.
    pass
