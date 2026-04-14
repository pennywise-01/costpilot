"""add dashboards table

Revision ID: 025
Revises: 024
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dashboards',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('slug', sa.String(128), nullable=False),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('layout_config', JSONB, nullable=False, server_default='[]'),
        sa.Column('previous_layout_config', JSONB, nullable=True),
        sa.Column('widget_config', JSONB, nullable=False, server_default='{}'),
        sa.Column('version_id', sa.Integer, nullable=False, server_default='1'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('updated_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_dashboards_org_slug'),
    )

    # Fast lookup of dashboards for an org (excludes soft-deleted)
    op.create_index(
        'idx_dashboards_org',
        'dashboards',
        ['organization_id'],
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    # Enforce exactly one default per org at the database level
    op.create_index(
        'idx_one_default_per_org',
        'dashboards',
        ['organization_id'],
        unique=True,
        postgresql_where=sa.text('is_default = TRUE AND deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('idx_one_default_per_org', table_name='dashboards')
    op.drop_index('idx_dashboards_org', table_name='dashboards')
    op.drop_table('dashboards')
