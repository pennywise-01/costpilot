"""add resource_config_snapshots table

Tier-2 asset/state inventory persistence. One row per cloud resource
captured during a daily config snapshot scan.

See plans/rule-data-source-strategy.md — Tier 2.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '028_add_resource_config_snapshots'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'resource_config_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cloud_account_id', sa.String(36), sa.ForeignKey('cloud_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cloud', sa.String(32), nullable=False),
        sa.Column('account_id', sa.String(256), nullable=False),
        sa.Column('source_service', sa.String(64), nullable=False),
        sa.Column('resource_id', sa.String(512), nullable=False),
        sa.Column('resource_type', sa.String(128), nullable=False),
        sa.Column('region', sa.String(64), nullable=False, server_default=''),
        sa.Column('properties', JSONB, nullable=True),
        sa.Column('tags', JSONB, nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            'cloud_account_id', 'resource_id', 'observed_at',
            name='uix_config_snapshots_dedup',
        ),
    )
    op.create_index('idx_config_snapshots_org', 'resource_config_snapshots', ['organization_id'])
    op.create_index('idx_config_snapshots_account', 'resource_config_snapshots', ['cloud_account_id'])
    op.create_index('idx_config_snapshots_type', 'resource_config_snapshots', ['resource_type'])
    op.create_index(
        'idx_config_snapshots_account_observed', 'resource_config_snapshots',
        ['cloud_account_id', 'observed_at'],
    )


def downgrade() -> None:
    op.drop_index('idx_config_snapshots_account_observed', table_name='resource_config_snapshots')
    op.drop_index('idx_config_snapshots_type', table_name='resource_config_snapshots')
    op.drop_index('idx_config_snapshots_account', table_name='resource_config_snapshots')
    op.drop_index('idx_config_snapshots_org', table_name='resource_config_snapshots')
    op.drop_table('resource_config_snapshots')
