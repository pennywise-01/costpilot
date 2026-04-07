"""fix user column defaults

Revision ID: 002
Revises: 001
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix is_active default - should be server_default not just default
    op.alter_column(
        "users",
        "is_active",
        server_default=sa.text("true"),
    )
    # Fix verified default
    op.alter_column(
        "users",
        "verified",
        server_default=sa.text("false"),
    )
    # Update existing users with NULL is_active to True
    op.execute("UPDATE users SET is_active = true WHERE is_active IS NULL")


def downgrade() -> None:
    op.alter_column("users", "is_active", server_default=None)
    op.alter_column("users", "verified", server_default=None)
