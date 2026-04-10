import asyncio
from app.database import async_session
from app.user_management.models import UserInvitation
from sqlalchemy import select

async def main():
    async with async_session() as db:
        result = await db.execute(
            select(UserInvitation)
            .where(UserInvitation.email == 'live-test-user@test.com')
            .order_by(UserInvitation.created_at.desc())
        )
        inv = result.scalar_one_or_none()
        if inv:
            print(f'TOKEN={inv.token}')
        else:
            print('NO_INVITATION_FOUND')

asyncio.run(main())
