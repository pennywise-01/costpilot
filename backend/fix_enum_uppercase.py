"""Add uppercase variants to permissionaction enum"""
import asyncio
import sys

sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url, isolation_level='AUTOCOMMIT')
    
    async with engine.connect() as conn:
        # Add uppercase values
        for val in ['READ', 'CREATE', 'UPDATE', 'DELETE', 'MANAGE']:
            try:
                await conn.execute(text(f"ALTER TYPE permissionaction ADD VALUE '{val}'"))
                print(f"Added '{val}'")
            except Exception as e:
                if 'already exists' in str(e):
                    print(f"'{val}' already exists")
                else:
                    raise
        
        # Also check rbacresourcetype
        result = await conn.execute(text("""
            SELECT enumlabel FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
            WHERE pg_type.typname = 'rbacresourcetype'
            ORDER BY pg_enum.enumsortorder
        """))
        values = [row[0] for row in result.fetchall()]
        print(f"\nCurrent rbacresourcetype values: {values}")
        
        # Add uppercase resource types if needed
        for val in ['ORGANIZATION', 'USER', 'CLOUD_ACCOUNT', 'POOL', 'EXPENSE', 'RESOURCE', 'RECOMMENDATION', 'RULE', 'NOTIFICATION', 'ENTERPRISE']:
            try:
                await conn.execute(text(f"ALTER TYPE rbacresourcetype ADD VALUE '{val}'"))
                print(f"Added '{val}' to rbacresourcetype")
            except Exception as e:
                if 'already exists' in str(e):
                    print(f"'{val}' already exists in rbacresourcetype")
                else:
                    raise
    
    await engine.dispose()
    print("\nDone")

if __name__ == '__main__':
    asyncio.run(main())
