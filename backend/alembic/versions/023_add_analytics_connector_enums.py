"""add analytics connector enum values and config column

Revision ID: 023
Revises: 022
Create Date: 2026-04-09

Adds new CloudType enum values for big data analytics platforms:
- bigquery (GCP BigQuery)
- redshift (AWS Redshift)
- athena (AWS Athena)
- synapse (Azure Synapse Analytics)

Also adds data_source_config JSON column to cloud_accounts for storing
analytics-specific configuration (dataset, table, query templates, etc.)
"""
from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add analytics connector enum values and config column."""
    
    conn = op.get_bind()
    
    # Add new enum values to cloudtype
    print("Adding analytics enum values to cloudtype...")
    
    new_values = ['bigquery', 'redshift', 'athena', 'synapse']
    
    for value in new_values:
        try:
            conn.execute(sa.text(f"""
                ALTER TYPE cloudtype ADD VALUE IF NOT EXISTS '{value}'
            """))
            conn.commit()
            print(f"✅ Added '{value}' to cloudtype enum")
        except Exception as e:
            print(f"⚠️  '{value}' may already exist: {e}")
    
    # Add data_source_config column for analytics-specific settings
    print("Adding data_source_config column to cloud_accounts...")
    
    conn.execute(sa.text("""
        ALTER TABLE cloud_accounts 
        ADD COLUMN IF NOT EXISTS data_source_config JSON
    """))
    conn.commit()
    print("✅ Added data_source_config column")
    
    # Add last_schema_sync column for tracking schema validation
    print("Adding last_schema_sync column to cloud_accounts...")
    
    conn.execute(sa.text("""
        ALTER TABLE cloud_accounts 
        ADD COLUMN IF NOT EXISTS last_schema_sync TIMESTAMP WITH TIME ZONE
    """))
    conn.commit()
    print("✅ Added last_schema_sync column")
    
    print("\n✅ Analytics connector schema migration complete!")


def downgrade() -> None:
    """Remove analytics enum values and columns (not recommended)."""
    
    conn = op.get_bind()
    
    # Note: PostgreSQL doesn't support removing enum values easily
    # We'll just drop the columns
    
    conn.execute(sa.text("""
        ALTER TABLE cloud_accounts 
        DROP COLUMN IF EXISTS data_source_config,
        DROP COLUMN IF EXISTS last_schema_sync
    """))
    
    conn.commit()
    print("⚠️  Removed analytics columns (enum values cannot be removed)")
