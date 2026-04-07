"""add export progress tracking columns

Revision ID: 016
Revises: 015
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def column_exists(op, table_name: str, column_name: str) -> bool:
    """Check if a column already exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table_name, "column": column_name},
    )
    return result.scalar() > 0


def upgrade() -> None:
    # Fix users.last_login to use TIMESTAMPTZ (timezone-aware)
    # This was broken by the datetime.utcnow() → utc_now() migration
    op.execute("ALTER TABLE users ALTER COLUMN last_login TYPE TIMESTAMPTZ USING last_login AT TIME ZONE 'UTC'")

    # Export progress tracking columns
    if not column_exists(op, "export_jobs", "progress_percent"):
        op.add_column("export_jobs", sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0.0"))
    if not column_exists(op, "export_jobs", "current_step"):
        op.add_column("export_jobs", sa.Column("current_step", sa.String(100), nullable=True))
    if not column_exists(op, "export_jobs", "total_records"):
        op.add_column("export_jobs", sa.Column("total_records", sa.Integer(), nullable=True))
    if not column_exists(op, "export_jobs", "processed_records"):
        op.add_column("export_jobs", sa.Column("processed_records", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    # Revert export progress columns
    if column_exists(op, "export_jobs", "processed_records"):
        op.drop_column("export_jobs", "processed_records")
    if column_exists(op, "export_jobs", "total_records"):
        op.drop_column("export_jobs", "total_records")
    if column_exists(op, "export_jobs", "current_step"):
        op.drop_column("export_jobs", "current_step")
    if column_exists(op, "export_jobs", "progress_percent"):
        op.drop_column("export_jobs", "progress_percent")

    # Revert last_login to naive timestamp
    op.execute("ALTER TABLE users ALTER COLUMN last_login TYPE TIMESTAMP USING last_login AT TIME ZONE 'UTC'")
