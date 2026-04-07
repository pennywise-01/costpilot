"""Reconcile user management schema drift

Revision ID: 006
Revises: 005
Create Date: 2026-04-01 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reconcile drift for existing tables that were created via create_all
    # before migrations were consistently applied.
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS department VARCHAR(128)")
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS job_title VARCHAR(128)")
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS joined_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_employees_department ON employees (department)")

    op.execute("ALTER TABLE rbac_user_roles ADD COLUMN IF NOT EXISTS assigned_by VARCHAR(36)")
    op.execute("ALTER TABLE rbac_user_roles ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE rbac_user_roles ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_rbac_user_roles_assigned_by'
            ) THEN
                ALTER TABLE rbac_user_roles
                    ADD CONSTRAINT fk_rbac_user_roles_assigned_by
                    FOREIGN KEY (assigned_by) REFERENCES users (id);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE rbac_user_roles DROP CONSTRAINT IF EXISTS fk_rbac_user_roles_assigned_by")
    op.execute("ALTER TABLE rbac_user_roles DROP COLUMN IF EXISTS expires_at")
    op.execute("ALTER TABLE rbac_user_roles DROP COLUMN IF EXISTS assigned_at")
    op.execute("ALTER TABLE rbac_user_roles DROP COLUMN IF EXISTS assigned_by")

    op.execute("DROP INDEX IF EXISTS ix_employees_department")
    op.execute("ALTER TABLE employees DROP COLUMN IF EXISTS joined_at")
    op.execute("ALTER TABLE employees DROP COLUMN IF EXISTS job_title")
    op.execute("ALTER TABLE employees DROP COLUMN IF EXISTS department")
