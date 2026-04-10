"""Quick diagnostic script using raw SQL"""
import asyncio
import sys

sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text


async def main():
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    
    # Use sync engine for simplicity
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(db_url)
    
    async with engine.connect() as conn:
        # Get users
        print(f"\n{'='*80}")
        print("USERS")
        print(f"{'='*80}")
        result = await conn.execute(text("SELECT id, email, display_name, status, role, is_active, verified FROM users WHERE deleted_at IS NULL"))
        users = result.fetchall()
        print(f"Total: {len(users)}\n")
        for u in users:
            print(f"ID: {u.id}")
            print(f"Email: {u.email}")
            print(f"Display Name: {u.display_name}")
            print(f"Status: {u.status}")
            print(f"Role: {u.role}")
            print(f"Active: {u.is_active}")
            print(f"Verified: {u.verified}")
            print(f"---")
        
        # Get organizations
        print(f"\n{'='*80}")
        print("ORGANIZATIONS")
        print(f"{'='*80}")
        result = await conn.execute(text("SELECT id, name, currency, pool_id, is_demo, disabled FROM organizations WHERE deleted_at IS NULL"))
        orgs = result.fetchall()
        print(f"Total: {len(orgs)}\n")
        for o in orgs:
            print(f"ID: {o.id}")
            print(f"Name: {o.name}")
            print(f"Currency: {o.currency}")
            print(f"Pool ID: {o.pool_id}")
            print(f"Is Demo: {o.is_demo}")
            print(f"---")
        
        # Get employees
        print(f"\n{'='*80}")
        print("EMPLOYEES (User-Organization Links)")
        print(f"{'='*80}")
        result = await conn.execute(text("""
            SELECT e.id, e.auth_user_id, e.organization_id, e.name, e.role, e.department, e.job_title,
                   u.email as user_email, o.name as org_name
            FROM employees e
            LEFT JOIN users u ON e.auth_user_id = u.id
            LEFT JOIN organizations o ON e.organization_id = o.id
            WHERE e.deleted_at IS NULL
        """))
        employees = result.fetchall()
        print(f"Total: {len(employees)}\n")
        for e in employees:
            print(f"Employee ID: {e.id}")
            print(f"User ID: {e.auth_user_id}")
            print(f"User Email: {e.user_email}")
            print(f"Organization ID: {e.organization_id}")
            print(f"Organization Name: {e.org_name}")
            print(f"Employee Name: {e.name}")
            print(f"Role: {e.role}")
            print(f"Department: {e.department}")
            print(f"Job Title: {e.job_title}")
            print(f"---")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
