import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings
from app.auth.service import hash_password


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    new_hash = hash_password("H4fz4n12@#")
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "UPDATE users SET hashed_password = :hp, "
                "failed_login_attempts = 0, locked_until = NULL "
                "WHERE email = :email"
            ),
            {"hp": new_hash, "email": "test@test.com"},
        )
        print(f"Updated {result.rowcount} row(s), hash length: {len(new_hash)}")
    await engine.dispose()


asyncio.run(main())
