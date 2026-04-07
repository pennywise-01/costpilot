#!/usr/bin/env python3
"""Diagnostic script to investigate missing cloud accounts for test@test.com"""

import asyncio
import os
import sys

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/costpilot")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.auth.models import User
from app.organizations.models import Employee, Organization
from app.cloud_accounts.models import CloudAccount


async def diagnose_user(email: str):
    """Diagnose cloud account access for a specific user email."""
    database_url = os.environ.get("DATABASE_URL")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print(f"\n{'='*60}")
        print(f"DIAGNOSING USER: {email}")
        print(f"{'='*60}\n")
        
        # 1. Find the user
        result = await session.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ ERROR: User with email '{email}' not found in database!")
            return
        
        print(f"✓ Found user:")
        print(f"  - ID: {user.id}")
        print(f"  - Email: {user.email}")
        print(f"  - Display Name: {user.display_name}")
        print(f"  - Is Active: {user.is_active}")
        print(f"  - Status: {user.status}")
        print()
        
        # 2. Find employee records (organization memberships)
        result = await session.execute(
            select(Employee, Organization)
            .join(Organization, Employee.organization_id == Organization.id)
            .where(
                Employee.auth_user_id == user.id,
                Employee.deleted_at.is_(None),
                Organization.deleted_at.is_(None)
            )
        )
        memberships = result.all()
        
        if not memberships:
            print(f"❌ ERROR: User '{email}' has no organization memberships!")
            print(f"   This means they cannot access any cloud accounts.")
            return
        
        print(f"✓ Found {len(memberships)} organization membership(s):")
        for employee, org in memberships:
            print(f"  - Organization: {org.name} (ID: {org.id})")
            print(f"    Employee ID: {employee.id}, Role: {employee.role}")
            print()
            
            # 3. Find cloud accounts for this organization
            result = await session.execute(
                select(CloudAccount).where(
                    CloudAccount.organization_id == org.id,
                    CloudAccount.deleted_at.is_(None)
                )
            )
            accounts = result.scalars().all()
            
            if not accounts:
                print(f"    ⚠️  No cloud accounts found for organization '{org.name}'")
            else:
                print(f"    ✓ Found {len(accounts)} cloud account(s):")
                for acc in accounts:
                    print(f"      - {acc.name} (Type: {acc.type.value}, ID: {acc.id})")
            print()
        
        # 4. Summary - check if there are ANY cloud accounts with this user's org
        result = await session.execute(
            select(CloudAccount).where(CloudAccount.deleted_at.is_(None))
        )
        all_accounts = result.scalars().all()
        print(f"📊 Summary:")
        print(f"  - Total cloud accounts in database: {len(all_accounts)}")
        print(f"  - User's accessible cloud accounts: {sum(len([a for a in all_accounts if a.organization_id == m[1].id]) for m in memberships)}")
        
        if not all_accounts:
            print(f"\n  ❌ NO CLOUD ACCOUNTS EXIST IN THE DATABASE!")
            print(f"     The user needs to connect a data source first.")
        elif not memberships:
            print(f"\n  ❌ USER HAS NO ORGANIZATION MEMBERSHIPS!")
            print(f"     They need to be added to an organization with cloud accounts.")


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "test@test.com"
    asyncio.run(diagnose_user(email))
