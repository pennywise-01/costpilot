"""Add MANAGE to permissionaction enum in database"""
import asyncio
import sys

sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url)
    
    async with engine.begin() as conn:
        # Add MANAGE to the permissionaction enum
        await conn.execute(text("ALTER TYPE permissionaction ADD VALUE IF NOT EXISTS 'manage'"))
        await conn.commit()
        print("Added 'manage' to permissionaction enum")
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
