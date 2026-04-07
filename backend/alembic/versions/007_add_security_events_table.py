"""Add security events table

Revision ID: 007
Revises: 006
Create Date: 2026-04-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the securityeventtype enum using raw SQL with IF NOT EXISTS
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'securityeventtype') THEN
                CREATE TYPE securityeventtype AS ENUM (
                    'SESSION_VALIDATION_FAILED',
                    'SESSION_BINDING_MISMATCH',
                    'SUSPICIOUS_IP_CHANGE',
                    'TOKEN_BLACKLISTED',
                    'RATE_LIMIT_EXCEEDED',
                    'INVALID_CREDENTIALS',
                    'ACCOUNT_LOCKED',
                    'FORCE_LOGOUT'
                );
            END IF;
        END
        $$;
    """)
    
    # Create security_events table only if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) REFERENCES users(id),
            event_type securityeventtype NOT NULL,
            ip_address_hash VARCHAR(64),
            user_agent TEXT,
            session_id VARCHAR(64),
            details TEXT,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMP WITHOUT TIME ZONE
        );
    """)
    
    # Create indexes only if they don't exist
    op.execute("CREATE INDEX IF NOT EXISTS ix_security_events_user_id ON security_events (user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_security_events_event_type ON security_events (event_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_security_events_session_id ON security_events (session_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_security_events_created_at ON security_events (created_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_security_events_user_id_created_at ON security_events (user_id, created_at);")


def downgrade() -> None:
    # Drop the table
    op.execute("DROP TABLE IF EXISTS security_events;")
    
    # Drop the enum only if it exists
    op.execute("DROP TYPE IF EXISTS securityeventtype;")
