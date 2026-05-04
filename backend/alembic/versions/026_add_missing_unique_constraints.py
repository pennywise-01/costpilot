"""Add missing unique constraints to prevent duplicate rows.

These constraints prevent the "Multiple rows were found when one or none
was required" errors that crash scalar_one_or_none() calls when duplicate
data accumulates over time.

Revision ID: 026
Revises: 025
"""
from alembic import op
import sqlalchemy as sa


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def _dedup(table: str, unique_cols: list[str], pk_col: str = "id") -> None:
    """Remove duplicate rows keeping the most recent one per unique column set."""
    # Build the dedup SQL: keep the row with the latest created_at per group
    cols_csv = ", ".join(unique_cols)
    op.execute(
        f"""
        DELETE FROM {table}
        WHERE {pk_col} NOT IN (
            SELECT MAX({pk_col})
            FROM {table}
            GROUP BY {cols_csv}
        )
        """
    )


def upgrade() -> None:
    # --- Deduplicate existing data before adding constraints ---

    # cost_cache: dedup by (organization_id, cache_type, cloud_account_id, period_start, period_end)
    # The period_end microsecond bug caused many duplicates; keep most recent
    _dedup("cost_cache", [
        "organization_id", "cache_type", "cloud_account_id",
        "period_start", "period_end",
    ])

    # employees: dedup by (auth_user_id, organization_id)
    _dedup("employees", ["auth_user_id", "organization_id"])

    # notification_preferences: dedup by (user_id, organization_id, notification_type)
    _dedup("notification_preferences", ["user_id", "organization_id", "notification_type"])

    # dashboards: dedup by (organization_id, slug)
    _dedup("dashboards", ["organization_id", "slug"])

    # --- Add unique constraints ---

    op.create_unique_constraint(
        "uq_employee_user_org",
        "employees",
        ["auth_user_id", "organization_id"],
    )

    op.create_unique_constraint(
        "uq_notification_pref_user_org_type",
        "notification_preferences",
        ["user_id", "organization_id", "notification_type"],
    )

    op.create_unique_constraint(
        "uq_dashboard_org_slug",
        "dashboards",
        ["organization_id", "slug"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_dashboard_org_slug", "dashboards", type_="unique")
    op.drop_constraint("uq_notification_pref_user_org_type", "notification_preferences", type_="unique")
    op.drop_constraint("uq_employee_user_org", "employees", type_="unique")
