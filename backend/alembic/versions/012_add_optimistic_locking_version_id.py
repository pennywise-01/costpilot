"""Add optimistic locking version_id to all mutable tables

Revision ID: 012
Revises: 011
Create Date: 2026-04-07 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All tables that now have OptimisticLockingMixin
TABLES = [
    "users",
    "organizations",
    "employees",
    "cloud_accounts",
    "pools",
    "pool_policies",
    "rules",
    "conditions",
    "recommendation_rules",
    "recommendation_rule_conditions",
    "notification_preferences",
    "rbac_roles",
    "rbac_role_permissions",
    "rbac_user_roles",
    "rbac_abac_policies",
    "rbac_access_reviews",
    "rbac_sso_configs",
    "scheduler_configs",
    "user_invitations",
    "user_preferences",
    "export_templates",
    "export_jobs",
    "scheduled_exports",
]


def upgrade() -> None:
    for table_name in TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "version_id",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )


def downgrade() -> None:
    for table_name in TABLES:
        op.drop_column(table_name, "version_id")
