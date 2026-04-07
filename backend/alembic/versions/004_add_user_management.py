"""Add user management tables

Revision ID: 004
Revises: 003_add_scheduler_tables
Create Date: 2025-03-31 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Add user status and security fields to users table ###
    op.add_column('users', sa.Column('status', sa.String(length=32), nullable=False, server_default='active'))
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_users_status'), 'users', ['status'], unique=False)
    
    # ### Create user_invitations table ###
    op.create_table('user_invitations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=256), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('invited_by', sa.String(length=36), nullable=False),
        sa.Column('role_id', sa.String(length=36), nullable=True),
        sa.Column('token', sa.String(length=512), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['rbac_roles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index(op.f('ix_user_invitations_email'), 'user_invitations', ['email'], unique=False)
    op.create_index(op.f('ix_user_invitations_organization_id'), 'user_invitations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_user_invitations_status'), 'user_invitations', ['status'], unique=False)
    op.create_index(op.f('ix_user_invitations_token'), 'user_invitations', ['token'], unique=True)
    
    # ### Create user_activity_logs table ###
    op.create_table('user_activity_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('resource_type', sa.String(length=64), nullable=True),
        sa.Column('resource_id', sa.String(length=36), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_activity_logs_action'), 'user_activity_logs', ['action'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_created_at'), 'user_activity_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_organization_id'), 'user_activity_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_user_id'), 'user_activity_logs', ['user_id'], unique=False)
    
    # ### Create user_preferences table ###
    op.create_table('user_preferences',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('notification_settings', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('dashboard_layout', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # ### Enhance employees table ###
    op.add_column('employees', sa.Column('department', sa.String(length=128), nullable=True))
    op.add_column('employees', sa.Column('job_title', sa.String(length=128), nullable=True))
    op.add_column('employees', sa.Column('joined_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_employees_department'), 'employees', ['department'], unique=False)
    
    # ### Enhance rbac_user_roles table ###
    op.add_column('rbac_user_roles', sa.Column('assigned_by', sa.String(length=36), nullable=True))
    op.add_column('rbac_user_roles', sa.Column('assigned_at', sa.DateTime(), nullable=True))
    op.add_column('rbac_user_roles', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_rbac_user_roles_assigned_by', 'rbac_user_roles', 'users', ['assigned_by'], ['id'])
    
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Remove rbac_user_roles enhancements ###
    op.drop_constraint('fk_rbac_user_roles_assigned_by', 'rbac_user_roles', type_='foreignkey')
    op.drop_column('rbac_user_roles', 'expires_at')
    op.drop_column('rbac_user_roles', 'assigned_at')
    op.drop_column('rbac_user_roles', 'assigned_by')
    
    # ### Remove employees enhancements ###
    op.drop_index(op.f('ix_employees_department'), table_name='employees')
    op.drop_column('employees', 'joined_at')
    op.drop_column('employees', 'job_title')
    op.drop_column('employees', 'department')
    
    # ### Drop user_preferences table ###
    op.drop_table('user_preferences')
    
    # ### Drop user_activity_logs table ###
    op.drop_index(op.f('ix_user_activity_logs_user_id'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_organization_id'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_created_at'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_action'), table_name='user_activity_logs')
    op.drop_table('user_activity_logs')
    
    # ### Drop user_invitations table ###
    op.drop_index(op.f('ix_user_invitations_token'), table_name='user_invitations')
    op.drop_index(op.f('ix_user_invitations_status'), table_name='user_invitations')
    op.drop_index(op.f('ix_user_invitations_organization_id'), table_name='user_invitations')
    op.drop_index(op.f('ix_user_invitations_email'), table_name='user_invitations')
    op.drop_table('user_invitations')
    
    # ### Remove users enhancements ###
    op.drop_index(op.f('ix_users_status'), table_name='users')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'status')
    # ### end Alembic commands ###
