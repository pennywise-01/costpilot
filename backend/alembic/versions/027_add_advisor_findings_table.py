"""add advisor_findings table

Revision ID: 027
Revises: 026
Create Date: 2026-05-04

Implements step 2 of plans/rule-data-source-strategy.md:
one normalized row per advisor/recommender finding, queryable by
the built-in recommendation rule engine.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'advisor_findings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column(
            'organization_id', sa.String(36),
            sa.ForeignKey('organizations.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'cloud_account_id', sa.String(36),
            sa.ForeignKey('cloud_accounts.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('cloud', sa.String(32), nullable=False),
        sa.Column('account_id', sa.String(256), nullable=False),
        sa.Column('source_service', sa.String(64), nullable=False),
        sa.Column('finding_type', sa.String(128), nullable=False),
        sa.Column('resource_id', sa.String(512), nullable=False, server_default=''),
        sa.Column('region', sa.String(64), nullable=False, server_default=''),
        sa.Column('severity', sa.String(16), nullable=False, server_default='medium'),
        sa.Column(
            'estimated_saving', sa.DECIMAL(15, 2),
            nullable=False, server_default='0',
        ),
        sa.Column('raw_payload', JSONB, nullable=True),
        sa.Column('builtin_rule_id', sa.String(64), nullable=True),
        sa.Column(
            'observed_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            'cloud_account_id', 'finding_type', 'resource_id', 'observed_at',
            name='uix_advisor_findings_dedup',
        ),
    )

    op.create_index(
        'idx_advisor_findings_org', 'advisor_findings', ['organization_id'],
    )
    op.create_index(
        'idx_advisor_findings_account', 'advisor_findings', ['cloud_account_id'],
    )
    op.create_index(
        'idx_advisor_findings_finding_type', 'advisor_findings', ['finding_type'],
    )
    op.create_index(
        'idx_advisor_findings_builtin_rule', 'advisor_findings', ['builtin_rule_id'],
    )
    op.create_index(
        'idx_advisor_findings_org_rule', 'advisor_findings',
        ['organization_id', 'builtin_rule_id'],
    )
    op.create_index(
        'idx_advisor_findings_account_observed', 'advisor_findings',
        ['cloud_account_id', 'observed_at'],
    )


def downgrade() -> None:
    op.drop_index('idx_advisor_findings_account_observed', table_name='advisor_findings')
    op.drop_index('idx_advisor_findings_org_rule', table_name='advisor_findings')
    op.drop_index('idx_advisor_findings_builtin_rule', table_name='advisor_findings')
    op.drop_index('idx_advisor_findings_finding_type', table_name='advisor_findings')
    op.drop_index('idx_advisor_findings_account', table_name='advisor_findings')
    op.drop_index('idx_advisor_findings_org', table_name='advisor_findings')
    op.drop_table('advisor_findings')
