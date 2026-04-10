"""Create test user in database"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, '/app')

from app.auth.service import hash_password
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url)
    
    email = "test@test.com"
    password = "H4fz4n12@#"
    hashed = hash_password(password)
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    async with engine.begin() as conn:
        # Check if user already exists
        check = await conn.execute(text('SELECT id FROM users WHERE email = :email'), {'email': email})
        existing = check.fetchone()
        
        if existing:
            # Update existing user's password
            await conn.execute(
                text('UPDATE users SET hashed_password = :pw WHERE email = :email'),
                {'pw': hashed, 'email': email}
            )
            print(f'Updated password for existing user: {email}')
        else:
            # Create new user - we need to get org_id first
            org_check = await conn.execute(text('SELECT id FROM organizations LIMIT 1'))
            org_row = org_check.fetchone()
            org_id = org_row.id if org_row else str(uuid.uuid4())
            
            if not org_row:
                # Create org first
                await conn.execute(
                    text("INSERT INTO organizations (id, name, status, created_at, updated_at) VALUES (:id, 'Test Org', 'active', :now, :now)"),
                    {'id': org_id, 'now': now}
                )
                print(f'Created organization: {org_id}')
            
            # Create user
            await conn.execute(
                text("INSERT INTO users (id, email, hashed_password, status, created_at, updated_at) VALUES (:id, :email, :pw, 'active', :now, :now)"),
                {'id': user_id, 'email': email, 'pw': hashed, 'now': now}
            )
            
            # Create org membership
            await conn.execute(
                text("INSERT INTO org_members (org_id, user_id, role, status, created_at, updated_at) VALUES (:org_id, :user_id, 'owner', 'active', :now, :now)"),
                {'org_id': org_id, 'user_id': user_id, 'now': now}
            )
            
            print(f'Created user: {email} with ID: {user_id}')
        
        await conn.commit()
    
    await engine.dispose()
    print('Done')

if __name__ == '__main__':
    asyncio.run(main())
