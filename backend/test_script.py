import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.organizations.models import Organization, Employee

engine = create_async_engine('postgresql+asyncpg://costpilot:costpilot@localhost:5432/costpilot')
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with async_session() as db:
        result = await db.execute(
            select(Organization, Employee.role)
            .join(Employee, Employee.organization_id == Organization.id)
            .limit(1)
        )
        rows = list(result.all())
        print(rows)
        for org, role in rows:
            print(f'Type of role: {type(role)}')
            try:
                print(f'Role value: {role.value}')
            except Exception as e:
                print(f'Error accessing role.value: {e}')

asyncio.run(main())
