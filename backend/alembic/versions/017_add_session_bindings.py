"""add session_bindings and security_events tables

Revision ID: 017
Revises: 016
Create Date: 2026-04-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('session_bindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoke_reason', sa.Enum('manual_logout', 'max_concurrent_sessions', 'admin_force_logout', 'suspicious_activity', name='sessionrevokereason'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )
    op.create_index(op.f('ix_session_bindings_user_id'), 'session_bindings', ['user_id'], unique=False)
    op.create_index(op.f('ix_session_bindings_session_id'), 'session_bindings', ['session_id'], unique=False)
    op.create_index(op.f('ix_session_bindings_expires_at'), 'session_bindings', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_bindings_expires_at'), table_name='session_bindings')
    op.drop_index(op.f('ix_session_bindings_session_id'), table_name='session_bindings')
    op.drop_index(op.f('ix_session_bindings_user_id'), table_name='session_bindings')
    op.drop_table('session_bindings')
