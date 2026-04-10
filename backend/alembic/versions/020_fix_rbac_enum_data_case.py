"""fix rbac enum data case and cleanup duplicate enum values

Revision ID: 020
Revises: 019
Create Date: 2026-04-09

This migration fixes the issue where RBAC enum data was saved with UPPERCASE
member names (MANAGE, READ, etc.) instead of lowercase values (manage, read, etc.).

Steps:
1. Convert all existing UPPERCASE enum data to lowercase
2. Delete duplicate UPPERCASE enum values from PostgreSQL enums
3. Ensure all future inserts use lowercase values
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Fix RBAC enum data case and cleanup duplicate enum values."""
    
    conn = op.get_bind()
    
    # Step 1: Convert existing UPPERCASE data to lowercase in rbac_role_permissions
    print("Converting rbac_role_permissions data to lowercase...")
    conn.execute(sa.text("""
        UPDATE rbac_role_permissions 
        SET action = LOWER(action::text)::permissionaction,
            resource_type = LOWER(resource_type::text)::rbacresourcetype,
            updated_at = NOW()
        WHERE action::text != LOWER(action::text) OR resource_type::text != LOWER(resource_type::text)
    """))
    conn.commit()
    print("✅ Converted rbac_role_permissions")
    
    # Step 2: Convert existing UPPERCASE data to lowercase in rbac_abac_policies
    print("Converting rbac_abac_policies data to lowercase...")
    conn.execute(sa.text("""
        UPDATE rbac_abac_policies 
        SET resource_type = LOWER(resource_type::text)::rbacresourcetype,
            action = LOWER(action::text)::permissionaction,
            operator = LOWER(operator::text)::abacoperator,
            updated_at = NOW()
        WHERE resource_type::text != LOWER(resource_type::text)
           OR action::text != LOWER(action::text)
           OR operator::text != LOWER(operator::text)
    """))
    conn.commit()
    print("✅ Converted rbac_abac_policies")
    
    # Step 3: Convert existing UPPERCASE data in rbac_access_reviews (if any)
    print("Converting rbac_access_reviews data to lowercase...")
    conn.execute(sa.text("""
        UPDATE rbac_access_reviews 
        SET status = LOWER(status::text)::accessreviewstatus,
            updated_at = NOW()
        WHERE status::text != LOWER(status::text)
    """))
    conn.commit()
    print("✅ Converted rbac_access_reviews")
    
    # Step 5: Remove duplicate UPPERCASE enum values from PostgreSQL enums
    print("Cleaning up duplicate enum values...")
    
    # permissionaction enum
    conn.execute(sa.text("""
        DELETE FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'permissionaction')
          AND enumlabel IN ('READ', 'CREATE', 'UPDATE', 'DELETE', 'MANAGE')
    """))
    conn.commit()
    print("✅ Cleaned up permissionaction enum")
    
    # rbacresourcetype enum
    conn.execute(sa.text("""
        DELETE FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'rbacresourcetype')
          AND enumlabel IN (
            'ORGANIZATION', 'CLOUD_ACCOUNT', 'POOL', 'EXPENSE', 'RESOURCE',
            'RECOMMENDATION', 'RULE', 'USER', 'NOTIFICATION', 'ENTERPRISE'
          )
    """))
    conn.commit()
    print("✅ Cleaned up rbacresourcetype enum")
    
    # accessreviewstatus enum
    conn.execute(sa.text("""
        DELETE FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'accessreviewstatus')
          AND enumlabel IN ('PENDING', 'APPROVED', 'REVOKED')
    """))
    conn.commit()
    print("✅ Cleaned up accessreviewstatus enum")
    
    # abacoperator enum
    conn.execute(sa.text("""
        DELETE FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'abacoperator')
          AND enumlabel IN ('EQUALS', 'NOT_EQUALS', 'IN', 'NOT_IN', 'CONTAINS', 'STARTS_WITH')
    """))
    conn.commit()
    print("✅ Cleaned up abacoperator enum")
    
    print("\n✅ All RBAC enum data and definitions cleaned up successfully!")


def downgrade() -> None:
    """Revert the data conversion (not recommended)."""
    
    conn = op.get_bind()
    
    # Reconvert lowercase data back to uppercase
    conn.execute(sa.text("""
        UPDATE rbac_role_permissions 
        SET action = UPPER(action),
            resource_type = UPPER(resource_type),
            updated_at = NOW()
        WHERE action = LOWER(action) AND resource_type = LOWER(resource_type)
    """))
    
    conn.execute(sa.text("""
        UPDATE rbac_abac_policies 
        SET resource_type = UPPER(resource_type),
            action = UPPER(action),
            operator = UPPER(operator),
            updated_at = NOW()
        WHERE resource_type = LOWER(resource_type) 
           AND action = LOWER(action)
           AND operator = LOWER(operator)
    """))
    
    conn.execute(sa.text("""
        UPDATE rbac_access_reviews 
        SET status = UPPER(status),
            updated_at = NOW()
        WHERE status = LOWER(status)
    """))
    
    conn.commit()
    print("⚠️  Reverted data to UPPERCASE (not recommended)")
