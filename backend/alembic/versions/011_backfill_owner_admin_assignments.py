"""Backfill owner admin assignments for legacy organizations

Revision ID: 011
Revises: 010
Create Date: 2026-04-06 16:55:00.000000

"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNER_ROLE_ALIASES = (
    "Organization Admin",
    "Organization Owner",
)


def _fetch_owner_role_id(bind, org_id: str) -> str | None:
    for role_name in OWNER_ROLE_ALIASES:
        row = bind.execute(
            sa.text(
                """
                SELECT id
                FROM rbac_roles
                WHERE organization_id = :org_id
                  AND name = :role_name
                  AND deleted_at IS NULL
                ORDER BY created_at
                LIMIT 1
                """
            ),
            {"org_id": org_id, "role_name": role_name},
        ).mappings().first()
        if row:
            return row["id"]

    return None


def _fetch_creator_user_id(bind, org_id: str) -> str | None:
    row = bind.execute(
        sa.text(
            """
            SELECT auth_user_id
            FROM employees
            WHERE organization_id = :org_id
              AND deleted_at IS NULL
              AND auth_user_id IS NOT NULL
            ORDER BY
              CASE WHEN role = 'optscale_manager' THEN 0 ELSE 1 END,
              CASE WHEN joined_at IS NULL THEN 1 ELSE 0 END,
              joined_at,
              created_at
            LIMIT 1
            """
        ),
        {"org_id": org_id},
    ).mappings().first()

    if not row:
        return None
    return row["auth_user_id"]


def _ensure_owner_assignment(
    bind,
    org_id: str,
    owner_role_id: str,
    creator_user_id: str,
    now: datetime,
) -> None:
    existing_assignment = bind.execute(
        sa.text(
            """
            SELECT id, deleted_at
            FROM rbac_user_roles
            WHERE organization_id = :org_id
              AND user_id = :user_id
              AND role_id = :role_id
            ORDER BY
              CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END,
              created_at
            LIMIT 1
            """
        ),
        {
            "org_id": org_id,
            "user_id": creator_user_id,
            "role_id": owner_role_id,
        },
    ).mappings().first()

    if existing_assignment:
        if existing_assignment["deleted_at"] is not None:
            bind.execute(
                sa.text(
                    """
                    UPDATE rbac_user_roles
                    SET deleted_at = NULL,
                        assigned_by = COALESCE(assigned_by, :assigned_by),
                        assigned_at = COALESCE(assigned_at, :assigned_at),
                        updated_at = :now
                    WHERE id = :assignment_id
                    """
                ),
                {
                    "assignment_id": existing_assignment["id"],
                    "assigned_by": creator_user_id,
                    "assigned_at": now,
                    "now": now,
                },
            )
        return

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
                NULL
            )
            """
        ),
        {
            "id": str(uuid4()),
            "now": now,
            "user_id": creator_user_id,
            "role_id": owner_role_id,
            "org_id": org_id,
            "assigned_by": creator_user_id,
            "assigned_at": now,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    required_tables = {
        "organizations",
        "employees",
        "rbac_roles",
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
        active_assignment = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM rbac_user_roles
                WHERE organization_id = :org_id
                  AND deleted_at IS NULL
                LIMIT 1
                """
            ),
            {"org_id": org_id},
        ).first()
        if active_assignment:
            continue

        owner_role_id = _fetch_owner_role_id(bind, org_id)
        if not owner_role_id:
            continue

        creator_user_id = _fetch_creator_user_id(bind, org_id)
        if not creator_user_id:
            continue

        _ensure_owner_assignment(
            bind,
            org_id=org_id,
            owner_role_id=owner_role_id,
            creator_user_id=creator_user_id,
            now=datetime.now(timezone.utc),
        )


def downgrade() -> None:
    # Backfill migration is intentionally not reverted automatically.
    pass
