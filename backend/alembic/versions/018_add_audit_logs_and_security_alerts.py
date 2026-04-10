"""add audit_logs and security_alerts tables

Revision ID: 018
Revises: 017
Create Date: 2026-04-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '018'
down_revision: Union[str, None] = '017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False, server_default='info'),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('organization_id', sa.String(36), nullable=True),
        sa.Column('resource_type', sa.String(64), nullable=True),
        sa.Column('resource_id', sa.String(36), nullable=True),
        sa.Column('action_details', sa.Text, nullable=True),
        sa.Column('ip_address_hash', sa.String(32), nullable=True),
        sa.Column('user_agent_hash', sa.String(32), nullable=True),
        sa.Column('session_id', sa.String(64), nullable=True),
        sa.Column('success', sa.Boolean, nullable=False, server_default='true'),
    )
    
    # Create indexes for audit_logs
    op.create_index('idx_audit_logs_timestamp_type', 'audit_logs', ['timestamp', 'event_type'])
    op.create_index('idx_audit_logs_org_event', 'audit_logs', ['organization_id', 'event_type'])
    op.create_index('idx_audit_logs_user_event', 'audit_logs', ['user_id', 'event_type'])
    op.create_index('idx_audit_logs_severity', 'audit_logs', ['severity', 'timestamp'])
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'])
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'])
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'])
    
    # Create security_alerts table
    op.create_table(
        'security_alerts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('organization_id', sa.String(36), nullable=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('details', sa.Text, nullable=True),
        sa.Column('acknowledged', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('acknowledged_by', sa.String(36), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('security_alerts')
    op.drop_index('idx_audit_logs_severity', table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_organization_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_index('idx_audit_logs_user_event', table_name='audit_logs')
    op.drop_index('idx_audit_logs_org_event', table_name='audit_logs')
    op.drop_index('idx_audit_logs_timestamp_type', table_name='audit_logs')
    op.drop_table('audit_logs')
