"""Add data export tables

Revision ID: 005
Revises: 004_add_user_management
Create Date: 2025-03-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Create export_templates table ###
    op.create_table('export_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data_type', sa.String(length=64), nullable=False),  # expenses, resources, recommendations, etc.
        sa.Column('format', sa.String(length=32), nullable=False),  # csv, json, parquet, pdf
        sa.Column('columns', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('date_range_days', sa.Integer(), nullable=True),  # null means all time
        sa.Column('group_by', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('sort_by', sa.String(length=128), nullable=True),
        sa.Column('sort_order', sa.String(length=10), nullable=True, server_default='desc'),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_export_templates_organization_id'), 'export_templates', ['organization_id'], unique=False)
    op.create_index(op.f('ix_export_templates_data_type'), 'export_templates', ['data_type'], unique=False)
    
    # ### Create export_jobs table ###
    op.create_table('export_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=True),  # null for ad-hoc exports
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('data_type', sa.String(length=64), nullable=False),
        sa.Column('format', sa.String(length=32), nullable=False),
        sa.Column('columns', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('filters', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('date_range_start', sa.DateTime(), nullable=True),
        sa.Column('date_range_end', sa.DateTime(), nullable=True),
        sa.Column('group_by', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('sort_by', sa.String(length=128), nullable=True),
        sa.Column('sort_order', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),  # pending, processing, completed, failed
        sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('record_count', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('file_url', sa.String(length=1024), nullable=True),
        sa.Column('file_path', sa.String(length=1024), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),  # File deletion date
        sa.Column('is_scheduled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('schedule_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('delivery_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),  # s3, gcs, azure, email
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['export_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_export_jobs_organization_id'), 'export_jobs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_export_jobs_template_id'), 'export_jobs', ['template_id'], unique=False)
    op.create_index(op.f('ix_export_jobs_status'), 'export_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_export_jobs_created_at'), 'export_jobs', ['created_at'], unique=False)
    op.create_index(op.f('ix_export_jobs_data_type'), 'export_jobs', ['data_type'], unique=False)
    
    # ### Create scheduled_exports table for recurring exports ###
    op.create_table('scheduled_exports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('delivery_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['export_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_exports_organization_id'), 'scheduled_exports', ['organization_id'], unique=False)
    op.create_index(op.f('ix_scheduled_exports_is_active'), 'scheduled_exports', ['is_active'], unique=False)
    op.create_index(op.f('ix_scheduled_exports_next_run_at'), 'scheduled_exports', ['next_run_at'], unique=False)
    
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Drop scheduled_exports table ###
    op.drop_index(op.f('ix_scheduled_exports_next_run_at'), table_name='scheduled_exports')
    op.drop_index(op.f('ix_scheduled_exports_is_active'), table_name='scheduled_exports')
    op.drop_index(op.f('ix_scheduled_exports_organization_id'), table_name='scheduled_exports')
    op.drop_table('scheduled_exports')
    
    # ### Drop export_jobs table ###
    op.drop_index(op.f('ix_export_jobs_data_type'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_created_at'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_status'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_template_id'), table_name='export_jobs')
    op.drop_index(op.f('ix_export_jobs_organization_id'), table_name='export_jobs')
    op.drop_table('export_jobs')
    
    # ### Drop export_templates table ###
    op.drop_index(op.f('ix_export_templates_data_type'), table_name='export_templates')
    op.drop_index(op.f('ix_export_templates_organization_id'), table_name='export_templates')
    op.drop_table('export_templates')
    # ### end Alembic commands ###
