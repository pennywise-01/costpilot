"""Reset password for test user"""
import asyncio
import sys

sys.path.insert(0, '/app')

from app.auth.service import hash_password
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url)
    
    hashed = hash_password('H4fz4n12@#')
    
    async with engine.begin() as conn:
        result = await conn.execute(
            text('UPDATE users SET hashed_password = :pw WHERE email = :email'),
            {'pw': hashed, 'email': 'test@test.com'}
        )
        print(f'Updated {result.rowcount} rows')
        await conn.commit()
    
    await engine.dispose()
    print('Password reset complete')

if __name__ == '__main__':
    asyncio.run(main())
