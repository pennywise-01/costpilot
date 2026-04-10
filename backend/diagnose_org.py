"""Quick diagnostic script to check database state"""
import asyncio
import sys

sys.path.insert(0, '/app')

from app.database import async_session
from app.auth.models import User
from app.organizations.models import Organization, Employee
from sqlalchemy import select


async def main():
    async with async_session() as session:
        # Get users
        users_result = await session.execute(select(User).where(User.deleted_at.is_(None)))
        users = users_result.scalars().all()
        
        print(f"\n{'='*80}")
        print(f"USERS (Total: {len(users)})")
        print(f"{'='*80}")
        for u in users:
            print(f"ID: {u.id}")
            print(f"Email: {u.email}")
            print(f"Display Name: {u.display_name}")
            print(f"Status: {u.status}")
            print(f"Role: {u.role.value}")
            print(f"---")
        
        # Get organizations
        orgs_result = await session.execute(select(Organization).where(Organization.deleted_at.is_(None)))
        orgs = orgs_result.scalars().all()
        
        print(f"\n{'='*80}")
        print(f"ORGANIZATIONS (Total: {len(orgs)})")
        print(f"{'='*80}")
        for o in orgs:
            print(f"ID: {o.id}")
            print(f"Name: {o.name}")
            print(f"Currency: {o.currency}")
            print(f"Pool ID: {o.pool_id}")
            print(f"---")
        
        # Get employees
        employees_result = await session.execute(select(Employee).where(Employee.deleted_at.is_(None)))
        employees = employees_result.scalars().all()
        
        print(f"\n{'='*80}")
        print(f"EMPLOYEES (User-Organization Links) (Total: {len(employees)})")
        print(f"{'='*80}")
        for e in employees:
            # Find the user email for this employee
            user_result = await session.execute(select(User).where(User.id == e.auth_user_id))
            user = user_result.scalar_one_or_none()
            
            # Find the org name for this employee
            org_result = await session.execute(select(Organization).where(Organization.id == e.organization_id))
            org = org_result.scalar_one_or_none()
            
            print(f"Employee ID: {e.id}")
            print(f"User: {e.auth_user_id} ({user.email if user else 'UNKNOWN'})")
            print(f"Organization: {e.organization_id} ({org.name if org else 'UNKNOWN'})")
            print(f"Employee Name: {e.name}")
            print(f"Role: {e.role.value}")
            print(f"---")


if __name__ == "__main__":
    asyncio.run(main())
