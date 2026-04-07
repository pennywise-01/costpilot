"""Add dead letter jobs table

Revision ID: 014
Revises: 013_add_missing_indexes
Create Date: 2026-04-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dead_letter_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scheduler_config_id', sa.String(length=36), nullable=False),
        sa.Column('original_run_id', sa.String(length=36), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('scheduled_retry_at', sa.DateTime(), nullable=True),
        sa.Column('last_retried_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('version_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dead_letter_jobs_scheduler_config_id'), 'dead_letter_jobs', ['scheduler_config_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dead_letter_jobs_scheduler_config_id'), table_name='dead_letter_jobs')
    op.drop_table('dead_letter_jobs')
