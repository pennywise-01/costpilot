"""add server defaults to created_at and updated_at columns

Revision ID: 021
Revises: 020
Create Date: 2026-04-09

This migration adds missing server defaults (NOW()) for created_at and updated_at
columns on tables that were missing them, causing IntegrityError when inserting
records without explicit timestamps.

Affected tables:
- export_jobs
- user_invitations
- user_preferences
- user_activity_logs
- export_templates
- scheduled_exports
"""
from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add server defaults to created_at and updated_at columns."""
    
    conn = op.get_bind()
    
    tables_to_fix = [
        'export_jobs',
        'user_invitations',
        'user_preferences',
        'user_activity_logs',
        'export_templates',
        'scheduled_exports',
    ]
    
    # Tables with BOTH created_at and updated_at
    tables_with_both = [
        'export_jobs',
        'user_invitations',
        'user_preferences',
        'export_templates',
        'scheduled_exports',
    ]
    
    # Tables with ONLY created_at
    tables_with_created_at_only = [
        'user_activity_logs',
    ]
    
    for table_name in tables_with_both:
        print(f"Fixing {table_name}...")
        
        # Add default to created_at
        conn.execute(sa.text(f"""
            ALTER TABLE {table_name} 
            ALTER COLUMN created_at SET DEFAULT NOW()
        """))
        conn.commit()
        
        # Add default to updated_at
        conn.execute(sa.text(f"""
            ALTER TABLE {table_name} 
            ALTER COLUMN updated_at SET DEFAULT NOW()
        """))
        conn.commit()
        
        # Create function
        conn.execute(sa.text(f"""
            CREATE OR REPLACE FUNCTION update_{table_name}_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        conn.commit()
        
        # Drop trigger
        conn.execute(sa.text(f"""
            DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name};
        """))
        conn.commit()
        
        # Create trigger
        conn.execute(sa.text(f"""
            CREATE TRIGGER trg_{table_name}_updated_at
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION update_{table_name}_updated_at();
        """))
        conn.commit()
        
        print(f"✅ Fixed {table_name}")
    
    for table_name in tables_with_created_at_only:
        print(f"Fixing {table_name} (created_at only)...")
        
        # Add default to created_at
        conn.execute(sa.text(f"""
            ALTER TABLE {table_name} 
            ALTER COLUMN created_at SET DEFAULT NOW()
        """))
        conn.commit()
        
        print(f"✅ Fixed {table_name}")
    
    print("\n✅ All table timestamp defaults added successfully!")


def downgrade() -> None:
    """Remove server defaults (not recommended)."""
    
    conn = op.get_bind()
    
    tables_to_fix = [
        'export_jobs',
        'user_invitations',
        'user_preferences',
        'user_activity_logs',
        'export_templates',
        'scheduled_exports',
    ]
    
    for table_name in tables_to_fix:
        conn.execute(sa.text(f"""
            ALTER TABLE {table_name} 
            ALTER COLUMN created_at DROP DEFAULT
        """))
        
        conn.execute(sa.text(f"""
            ALTER TABLE {table_name} 
            ALTER COLUMN updated_at DROP DEFAULT
        """))
        
        conn.execute(sa.text(f"""
            DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name};
            DROP FUNCTION IF EXISTS update_{table_name}_updated_at();
        """))
        
        conn.commit()
    
    print("⚠️  Removed timestamp defaults (not recommended)")
