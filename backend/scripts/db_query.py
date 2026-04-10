"""
Database query script for CostPilot
Usage:
  - List all registered users
  - List all organizations
  - Create a new organization
  - Create a new user

Run from backend directory:
  python scripts/db_query.py --list-users
  python scripts/db_query.py --list-orgs
  python scripts/db_query.py --create-org --name "My Org" --currency USD
  python scripts/db_query.py --create-user --email "user@example.com" --name "John Doe" --password "securepassword"
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime
from uuid import uuid4

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.auth.models import User
from app.organizations.models import Organization, Employee
from app.shared.enums import RolePurpose, UserStatus
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def list_users():
    """List all registered users from the database."""
    async with async_session() as session:
        async with session.begin():
            # Query all users (excluding soft-deleted)
            stmt = (
                select(User)
                .where(User.deleted_at.is_(None))
                .order_by(User.created_at.desc())
            )
            result = await session.execute(stmt)
            users = result.scalars().all()

            print(f"\n{'='*80}")
            print(f"REGISTERED USERS (Total: {len(users)})")
            print(f"{'='*80}")
            
            if not users:
                print("No users found in the database.")
                return

            print(f"{'ID':<38} {'Email':<35} {'Name':<25} {'Role':<20} {'Status':<12} {'Verified':<10} {'Created At'}")
            print(f"{'-'*38} {'-'*35} {'-'*25} {'-'*20} {'-'*12} {'-'*10} {'-'*20}")
            
            for user in users:
                print(f"{user.id:<38} {user.email:<35} {user.display_name:<25} {user.role.value:<20} {user.status:<12} {str(user.verified):<10} {user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else 'N/A'}")
            
            print(f"{'='*80}\n")


async def list_organizations():
    """List all organizations from the database."""
    async with async_session() as session:
        async with session.begin():
            # Query all organizations (excluding soft-deleted)
            stmt = (
                select(Organization)
                .where(Organization.deleted_at.is_(None))
                .order_by(Organization.created_at.desc())
            )
            result = await session.execute(stmt)
            orgs = result.scalars().all()

            print(f"\n{'='*100}")
            print(f"ORGANIZATIONS (Total: {len(orgs)})")
            print(f"{'='*100}")
            
            if not orgs:
                print("No organizations found in the database.")
                return

            print(f"{'ID':<38} {'Name':<30} {'Currency':<10} {'Pool ID':<38} {'Demo':<6} {'Disabled':<10} {'Created At'}")
            print(f"{'-'*38} {'-'*30} {'-'*10} {'-'*38} {'-'*6} {'-'*10} {'-'*20}")
            
            for org in orgs:
                print(f"{org.id:<38} {org.name:<30} {org.currency:<10} {str(org.pool_id or 'N/A'):<38} {str(org.is_demo):<6} {str(org.disabled):<10} {org.created_at.strftime('%Y-%m-%d %H:%M:%S') if org.created_at else 'N/A'}")
            
            print(f"{'='*100}\n")


async def create_organization(name: str, currency: str = "USD", is_demo: bool = False):
    """Create a new organization in the database."""
    org_id = str(uuid4())
    
    async with async_session() as session:
        async with session.begin():
            # Create new organization
            new_org = Organization(
                id=org_id,
                name=name,
                currency=currency,
                is_demo=is_demo,
                disabled=False
            )
            
            session.add(new_org)
            await session.flush()
            
            print(f"\n{'='*80}")
            print(f"ORGANIZATION CREATED SUCCESSFULLY")
            print(f"{'='*80}")
            print(f"ID:         {org_id}")
            print(f"Name:       {name}")
            print(f"Currency:   {currency}")
            print(f"Demo:       {is_demo}")
            print(f"Created At: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}\n")
            
            return org_id


async def create_user(
    email: str, 
    display_name: str, 
    password: str,
    role: str = "optscale_member",
    is_active: bool = True,
    verified: bool = False,
    status: str = "active"
):
    """Create a new user in the database."""
    user_id = str(uuid4())
    hashed_password = pwd_context.hash(password)
    
    async with async_session() as session:
        async with session.begin():
            # Check if user with this email already exists
            check_stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
            result = await session.execute(check_stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"\n❌ ERROR: User with email '{email}' already exists!")
                return None
            
            # Create new user
            new_user = User(
                id=user_id,
                email=email,
                display_name=display_name,
                hashed_password=hashed_password,
                role=RolePurpose(role),
                is_active=is_active,
                verified=verified,
                status=status
            )
            
            session.add(new_user)
            await session.flush()
            
            print(f"\n{'='*80}")
            print(f"USER CREATED SUCCESSFULLY")
            print(f"{'='*80}")
            print(f"ID:         {user_id}")
            print(f"Email:      {email}")
            print(f"Name:       {display_name}")
            print(f"Role:       {role}")
            print(f"Active:     {is_active}")
            print(f"Verified:   {verified}")
            print(f"Status:     {status}")
            print(f"Created At: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}\n")
            
            return user_id


async def add_user_to_organization(user_id: str, organization_id: str, name: str, role: str = "optscale_member"):
    """Add an existing user to an organization (create Employee record)."""
    employee_id = str(uuid4())
    
    async with async_session() as session:
        async with session.begin():
            # Check if user exists
            user_stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                print(f"\n❌ ERROR: User with ID '{user_id}' not found!")
                return None
            
            # Check if organization exists
            org_stmt = select(Organization).where(Organization.id == organization_id, Organization.deleted_at.is_(None))
            org_result = await session.execute(org_stmt)
            org = org_result.scalar_one_or_none()
            
            if not org:
                print(f"\n❌ ERROR: Organization with ID '{organization_id}' not found!")
                return None
            
            # Create employee record
            new_employee = Employee(
                id=employee_id,
                name=name,
                organization_id=organization_id,
                auth_user_id=user_id,
                role=RolePurpose(role)
            )
            
            session.add(new_employee)
            await session.flush()
            
            print(f"\n{'='*80}")
            print(f"USER ADDED TO ORGANIZATION")
            print(f"{'='*80}")
            print(f"Employee ID:    {employee_id}")
            print(f"User ID:        {user_id}")
            print(f"User Email:     {user.email}")
            print(f"Organization:   {org.name}")
            print(f"Role:           {role}")
            print(f"{'='*80}\n")
            
            return employee_id


def main():
    parser = argparse.ArgumentParser(description="CostPilot Database Query Tool")
    
    # List operations
    parser.add_argument('--list-users', action='store_true', help='List all registered users')
    parser.add_argument('--list-orgs', action='store_true', help='List all organizations')
    
    # Create operations
    parser.add_argument('--create-org', action='store_true', help='Create a new organization')
    parser.add_argument('--name', type=str, help='Organization or user name')
    parser.add_argument('--currency', type=str, default='USD', help='Currency code (default: USD)')
    parser.add_argument('--demo', action='store_true', help='Mark organization as demo')
    
    parser.add_argument('--create-user', action='store_true', help='Create a new user')
    parser.add_argument('--email', type=str, help='User email address')
    parser.add_argument('--password', type=str, help='User password')
    parser.add_argument('--role', type=str, default='optscale_member', 
                       choices=['optscale_member', 'optscale_engineer', 'optscale_manager'],
                       help='User role (default: optscale_member)')
    parser.add_argument('--verified', action='store_true', help='Mark user as verified')
    
    # Link operations
    parser.add_argument('--add-to-org', action='store_true', help='Add user to organization')
    parser.add_argument('--user-id', type=str, help='User ID')
    parser.add_argument('--org-id', type=str, help='Organization ID')
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    
    # Run the appropriate operation
    if args.list_users:
        asyncio.run(list_users())
    
    elif args.list_orgs:
        asyncio.run(list_organizations())
    
    elif args.create_org:
        if not args.name:
            print("❌ ERROR: --name is required for creating an organization")
            sys.exit(1)
        asyncio.run(create_organization(args.name, args.currency, args.demo))
    
    elif args.create_user:
        if not args.email or not args.name or not args.password:
            print("❌ ERROR: --email, --name, and --password are required for creating a user")
            sys.exit(1)
        asyncio.run(create_user(
            email=args.email,
            display_name=args.name,
            password=args.password,
            role=args.role,
            verified=args.verified
        ))
    
    elif args.add_to_org:
        if not args.user_id or not args.org_id or not args.name:
            print("❌ ERROR: --user-id, --org-id, and --name are required")
            sys.exit(1)
        asyncio.run(add_user_to_organization(args.user_id, args.org_id, args.name))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
