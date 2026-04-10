"""Check users in database"""
import asyncio
import sys

sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url)
    
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT id, email, status, created_at FROM users LIMIT 10'))
        rows = result.fetchall()
        if rows:
            print(f"Found {len(rows)} users:")
            for row in rows:
                print(f"  {row.id} | {row.email} | {row.status} | {row.created_at}")
        else:
            print("No users found in database")
    
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
