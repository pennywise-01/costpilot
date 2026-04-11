"""Fix securityeventtype enum casing to match Python model values

Revision ID: 024
Revises: 023
Create Date: 2026-04-11

The original migration 007 created the securityeventtype enum with
UPPERCASE values (e.g. 'SESSION_BINDING_MISMATCH'), but the Python
SecurityEventType enum uses lowercase string values (e.g.
'session_binding_mismatch'). This mismatch causes insert failures.

This migration recreates the enum with lowercase values to match
the Python model's values_callable.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename old enum type
    op.execute("ALTER TYPE securityeventtype RENAME TO securityeventtype_old")

    # Create new enum with lowercase values matching Python model
    op.execute("""
        CREATE TYPE securityeventtype AS ENUM (
            'session_validation_failed',
            'session_binding_mismatch',
            'suspicious_ip_change',
            'token_blacklisted',
            'rate_limit_exceeded',
            'invalid_credentials',
            'account_locked',
            'force_logout'
        )
    """)

    # Swap column to use new type (convert existing data to lowercase)
    op.execute("""
        ALTER TABLE security_events
            ALTER COLUMN event_type TYPE securityeventtype
            USING lower(event_type::text)::securityeventtype
    """)

    # Drop old type
    op.execute("DROP TYPE securityeventtype_old")


def downgrade() -> None:
    # Revert to uppercase enum values
    op.execute("ALTER TYPE securityeventtype RENAME TO securityeventtype_old")

    op.execute("""
        CREATE TYPE securityeventtype AS ENUM (
            'SESSION_VALIDATION_FAILED',
            'SESSION_BINDING_MISMATCH',
            'SUSPICIOUS_IP_CHANGE',
            'TOKEN_BLACKLISTED',
            'RATE_LIMIT_EXCEEDED',
            'INVALID_CREDENTIALS',
            'ACCOUNT_LOCKED',
            'FORCE_LOGOUT'
        )
    """)

    op.execute("""
        ALTER TABLE security_events
            ALTER COLUMN event_type TYPE securityeventtype
            USING upper(event_type::text)::securityeventtype
    """)

    op.execute("DROP TYPE securityeventtype_old")
