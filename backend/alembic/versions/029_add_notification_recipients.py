"""Add recipients column to notification_preferences.

Revision ID: 029
Revises: 028
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "029_add_notification_recipients"
down_revision = "028_add_resource_config_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("recipients", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "recipients")
