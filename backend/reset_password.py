"""Reset password for test user"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.security.password import hash_password
from app.shared.db.postgres import get_engine
from sqlalchemy import text

async def main():
    email = "test@test.com"
    new_password = "H4fz4n12@#"
    
    # Hash the password
    hashed = hash_password(new_password)
    
    # Get database URL from env
    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://costpilot:costpilot@localhost:5432/costpilot")
    # For direct connection to exposed port
    db_url = "postgresql+asyncpg://costpilot:costpilot@localhost:5432/costpilot"
    
    engine = get_engine(db_url)
    
    async with engine.begin() as conn:
        # Update password
        result = await conn.execute(
            text("UPDATE users SET password_hash = :password WHERE email = :email"),
            {"password": hashed, "email": email}
        )
        print(f"Updated {result.rowcount} rows for {email}")
        await conn.commit()
    
    await engine.dispose()
    print("Password reset complete")

if __name__ == "__main__":
    asyncio.run(main())
