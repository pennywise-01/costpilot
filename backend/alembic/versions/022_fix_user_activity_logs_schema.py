"""add missing columns to user_activity_logs

Revision ID: 022
Revises: 021
Create Date: 2026-04-09

The user_activity_logs table is missing columns that BaseModel expects:
- updated_at (from TimestampMixin)
- deleted_at (from SoftDeleteMixin)
- version_id (from OptimisticLockingMixin)

This migration adds these columns to fix ProgrammingError when inserting
activity logs.
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing columns to user_activity_logs table."""
    
    conn = op.get_bind()
    
    print("Adding missing columns to user_activity_logs...")
    
    # Add updated_at with default
    conn.execute(sa.text("""
        ALTER TABLE user_activity_logs 
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
    """))
    conn.commit()
    print("✅ Added updated_at")
    
    # Add deleted_at (nullable for soft deletes)
    conn.execute(sa.text("""
        ALTER TABLE user_activity_logs 
        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE
    """))
    conn.commit()
    print("✅ Added deleted_at")
    
    # Add version_id for optimistic locking
    conn.execute(sa.text("""
        ALTER TABLE user_activity_logs 
        ADD COLUMN IF NOT EXISTS version_id INTEGER DEFAULT 1 NOT NULL
    """))
    conn.commit()
    print("✅ Added version_id")
    
    # Add trigger for updated_at
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION update_user_activity_logs_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    conn.commit()
    
    conn.execute(sa.text("""
        DROP TRIGGER IF EXISTS trg_user_activity_logs_updated_at ON user_activity_logs;
    """))
    conn.commit()
    
    conn.execute(sa.text("""
        CREATE TRIGGER trg_user_activity_logs_updated_at
            BEFORE UPDATE ON user_activity_logs
            FOR EACH ROW
            EXECUTE FUNCTION update_user_activity_logs_updated_at();
    """))
    conn.commit()
    print("✅ Added updated_at trigger")
    
    # Add index on deleted_at for soft delete queries
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_user_activity_logs_deleted_at 
        ON user_activity_logs(deleted_at)
    """))
    conn.commit()
    print("✅ Added deleted_at index")
    
    print("\n✅ user_activity_logs table schema fixed!")


def downgrade() -> None:
    """Remove added columns (not recommended)."""
    
    conn = op.get_bind()
    
    conn.execute(sa.text("""
        DROP TRIGGER IF EXISTS trg_user_activity_logs_updated_at ON user_activity_logs;
        DROP FUNCTION IF EXISTS update_user_activity_logs_updated_at();
        ALTER TABLE user_activity_logs DROP COLUMN IF EXISTS updated_at;
        ALTER TABLE user_activity_logs DROP COLUMN IF EXISTS deleted_at;
        ALTER TABLE user_activity_logs DROP COLUMN IF EXISTS version_id;
    """))
    
    conn.commit()
    print("⚠️  Removed columns from user_activity_logs")
