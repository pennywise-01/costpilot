"""add trigger to sync employee name with user display name

Revision ID: 019
Revises: 018
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create a trigger that automatically updates employee.name when user.display_name changes.
    
    This ensures data consistency between the users and employees tables.
    When a user's display_name is updated, all their employee records (across
    organizations) will have their name field automatically updated as well.
    """
    
    # Create the trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_employee_name_with_user()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Update all non-deleted employee records for this user
            UPDATE employees 
            SET name = NEW.display_name,
                updated_at = NOW()
            WHERE auth_user_id = NEW.id 
              AND deleted_at IS NULL;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create the trigger on the users table
    op.execute("""
        CREATE TRIGGER trg_sync_employee_name_with_user
            AFTER UPDATE OF display_name ON users
            FOR EACH ROW
            WHEN (OLD.display_name IS DISTINCT FROM NEW.display_name)
            EXECUTE FUNCTION sync_employee_name_with_user();
    """)


def downgrade() -> None:
    """Remove the trigger and function."""
    
    # Drop the trigger
    op.execute("DROP TRIGGER IF EXISTS trg_sync_employee_name_with_user ON users")
    
    # Drop the function
    op.execute("DROP FUNCTION IF EXISTS sync_employee_name_with_user()")
