"""add missing indexes for query performance

Revision ID: 013
Revises: 012
Create Date: 2026-04-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def index_exists(op, index_name: str, table_name: str) -> bool:
    """Check if an index already exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM pg_indexes WHERE tablename = :table AND indexname = :index"
        ),
        {"table": table_name, "index": index_name},
    )
    return result.scalar() > 0


def upgrade() -> None:
    # rules.organization_id - used in every list_rules query
    if not index_exists(op, "ix_rules_organization_id", "rules"):
        op.create_index("ix_rules_organization_id", "rules", ["organization_id"])

    # conditions.rule_id - used when loading rule conditions
    if not index_exists(op, "ix_conditions_rule_id", "conditions"):
        op.create_index("ix_conditions_rule_id", "conditions", ["rule_id"])

    # employees.organization_id - used in list_employees
    if not index_exists(op, "ix_employees_organization_id", "employees"):
        op.create_index("ix_employees_organization_id", "employees", ["organization_id"])

    # employees.auth_user_id - used in list_organizations JOIN
    if not index_exists(op, "ix_employees_auth_user_id", "employees"):
        op.create_index("ix_employees_auth_user_id", "employees", ["auth_user_id"])

    # CostCache composite index for cache lookup queries
    if not index_exists(op, "ix_cost_cache_org_type_expires", "cost_cache"):
        op.create_index("ix_cost_cache_org_type_expires", "cost_cache", ["organization_id", "cache_type", "expires_at"])

    # RBAC user role assignments - individual lookups
    if not index_exists(op, "ix_user_roles_user_id", "rbac_user_roles"):
        op.create_index("ix_user_roles_user_id", "rbac_user_roles", ["user_id"])
    if not index_exists(op, "ix_user_roles_organization_id", "rbac_user_roles"):
        op.create_index("ix_user_roles_organization_id", "rbac_user_roles", ["organization_id"])

    # notification_preferences.user_id
    if not index_exists(op, "ix_notification_preferences_user_id", "notification_preferences"):
        op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])

    # scheduler_configs.organization_id
    if not index_exists(op, "ix_scheduler_configs_organization_id", "scheduler_configs"):
        op.create_index("ix_scheduler_configs_organization_id", "scheduler_configs", ["organization_id"])

    # export_jobs.organization_id
    if not index_exists(op, "ix_export_jobs_organization_id", "export_jobs"):
        op.create_index("ix_export_jobs_organization_id", "export_jobs", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_export_jobs_organization_id", table_name="export_jobs")
    op.drop_index("ix_scheduler_configs_organization_id", table_name="scheduler_configs")
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_index("ix_user_roles_organization_id", table_name="rbac_user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="rbac_user_roles")
    op.drop_index("ix_cost_cache_org_type_expires", table_name="cost_cache")
    op.drop_index("ix_employees_auth_user_id", table_name="employees")
    op.drop_index("ix_employees_organization_id", table_name="employees")
    op.drop_index("ix_conditions_rule_id", table_name="conditions")
    op.drop_index("ix_rules_organization_id", table_name="rules")
