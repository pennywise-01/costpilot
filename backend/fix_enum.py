"""Add MANAGE to permissionaction enum and verify"""
import asyncio
import sys

sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text

async def main():
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url, isolation_level='AUTOCOMMIT')
    
    async with engine.connect() as conn:
        # Check current enum values
        result = await conn.execute(text("""
            SELECT enumlabel FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
            WHERE pg_type.typname = 'permissionaction'
            ORDER BY pg_enum.enumsortorder
        """))
        values = [row[0] for row in result.fetchall()]
        print(f"Current enum values: {values}")
        
        if 'manage' not in values:
            # Add MANAGE in a separate transaction
            await conn.execute(text("ALTER TYPE permissionaction ADD VALUE 'manage'"))
            print("Added 'manage' to permissionaction enum")
        
        # Verify
        result = await conn.execute(text("""
            SELECT enumlabel FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
            WHERE pg_type.typname = 'permissionaction'
            ORDER BY pg_enum.enumsortorder
        """))
        values = [row[0] for row in result.fetchall()]
        print(f"Updated enum values: {values}")
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
