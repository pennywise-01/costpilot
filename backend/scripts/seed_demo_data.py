"""
Seed Demo Data Script

Creates a complete demo organization with proper, consistent data:
- User with meaningful display name
- Organization with realistic name
- Employee record linking user to organization
- Default RBAC roles
- Proper naming consistency

This script is idempotent - it checks if data exists before creating.

Usage:
    python scripts/seed_demo_data.py [--force]
    
Options:
    --force: Delete existing demo data and re-seed
"""
import asyncio
import sys
import argparse

sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.auth.service import hash_password


async def seed_demo_data(force=False):
    """Seed demo data with complete, consistent state."""
    
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url)
    
    # Configuration
    DEMO_EMAIL = "demo@costpilot.io"
    DEMO_PASSWORD = "DemoPass123!"
    DEMO_DISPLAY_NAME = "Demo Administrator"
    DEMO_ORG_NAME = "Acme Corporation"
    DEMO_CURRENCY = "USD"
    
    try:
        async with engine.begin() as conn:
            # Check if demo data already exists
            check_user = await conn.execute(text("""
                SELECT id FROM users WHERE email = :email AND deleted_at IS NULL
            """), {'email': DEMO_EMAIL})
            existing_user = check_user.fetchone()
            
            check_org = await conn.execute(text("""
                SELECT id FROM organizations WHERE name = :name AND deleted_at IS NULL
            """), {'name': DEMO_ORG_NAME})
            existing_org = check_org.fetchone()
            
            if existing_user or existing_org:
                if force:
                    print("⚠️  --force flag detected, deleting existing demo data...")
                    
                    # Delete existing demo org (cascades to employees)
                    if existing_org:
                        await conn.execute(text("""
                            UPDATE organizations 
                            SET deleted_at = NOW(), updated_at = NOW()
                            WHERE name = :name AND deleted_at IS NULL
                        """), {'name': DEMO_ORG_NAME})
                        print(f"   ✅ Deleted organization '{DEMO_ORG_NAME}'")
                    
                    # Delete existing demo user
                    if existing_user:
                        await conn.execute(text("""
                            UPDATE users 
                            SET deleted_at = NOW(), updated_at = NOW()
                            WHERE email = :email AND deleted_at IS NULL
                        """), {'email': DEMO_EMAIL})
                        print(f"   ✅ Deleted user '{DEMO_EMAIL}'")
                    
                    await conn.commit()
                else:
                    print(f"⚠️  Demo data already exists:")
                    if existing_user:
                        print(f"   - User: {DEMO_EMAIL}")
                    if existing_org:
                        print(f"   - Organization: {DEMO_ORG_NAME}")
                    print(f"\nTo re-seed, use: python scripts/seed_demo_data.py --force")
                    return
            
            print(f"\n{'='*80}")
            print("SEEDING DEMO DATA")
            print(f"{'='*80}")
            
            # Step 1: Create user with meaningful display name
            print(f"\n1. Creating user: {DEMO_EMAIL}")
            hashed_pw = hash_password(DEMO_PASSWORD)
            
            await conn.execute(text("""
                INSERT INTO users (
                    id, email, display_name, hashed_password,
                    is_active, verified, role, status, version_id,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text,
                    :email,
                    :display_name,
                    :hashed_password,
                    true,
                    true,
                    'optscale_member',
                    'active',
                    1,
                    NOW(),
                    NOW()
                )
                RETURNING id, email, display_name
            """), {
                'email': DEMO_EMAIL,
                'display_name': DEMO_DISPLAY_NAME,
                'hashed_password': hashed_pw
            })
            
            # Get the user ID
            user_result = await conn.execute(text("""
                SELECT id FROM users WHERE email = :email AND deleted_at IS NULL
            """), {'email': DEMO_EMAIL})
            user_row = user_result.fetchone()
            
            if not user_row:
                raise Exception("Failed to create user")
            
            user_id = user_row.id
            print(f"   ✅ User created: ID={user_id}")
            
            await conn.commit()
            
            # Step 2: Create organization
            print(f"\n2. Creating organization: {DEMO_ORG_NAME}")
            
            await conn.execute(text("""
                INSERT INTO organizations (
                    id, name, currency, is_demo, disabled, version_id,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text,
                    :name,
                    :currency,
                    true,
                    false,
                    1,
                    NOW(),
                    NOW()
                )
                RETURNING id, name
            """), {
                'name': DEMO_ORG_NAME,
                'currency': DEMO_CURRENCY
            })
            
            # Get the org ID
            org_result = await conn.execute(text("""
                SELECT id FROM organizations WHERE name = :name AND deleted_at IS NULL
            """), {'name': DEMO_ORG_NAME})
            org_row = org_result.fetchone()
            
            if not org_row:
                raise Exception("Failed to create organization")
            
            org_id = org_row.id
            print(f"   ✅ Organization created: ID={org_id}")
            
            await conn.commit()
            
            # Step 3: Create employee record (links user to org)
            print(f"\n3. Creating employee record (user → organization link)")
            
            await conn.execute(text("""
                INSERT INTO employees (
                    id, name, organization_id, auth_user_id,
                    role, joined_at, version_id,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text,
                    :name,
                    :org_id,
                    :user_id,
                    'optscale_manager',
                    NOW(),
                    1,
                    NOW(),
                    NOW()
                )
            """), {
                'name': DEMO_DISPLAY_NAME,  # Matches user.display_name
                'org_id': org_id,
                'user_id': user_id
            })
            
            print(f"   ✅ Employee record created")
            
            await conn.commit()
            
            # Step 4: Create root pool
            print(f"\n4. Creating root pool for organization")
            
            await conn.execute(text("""
                INSERT INTO pools (
                    id, name, organization_id, "limit", purpose, version_id,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text,
                    :name,
                    :org_id,
                    0,
                    'budget',
                    1,
                    NOW(),
                    NOW()
                )
                RETURNING id
            """), {
                'name': DEMO_ORG_NAME,  # Pool name matches org name
                'org_id': org_id
            })
            
            pool_result = await conn.execute(text("""
                SELECT id FROM pools WHERE organization_id = :org_id AND deleted_at IS NULL
            """), {'org_id': org_id})
            pool_row = pool_result.fetchone()
            
            if pool_row:
                pool_id = pool_row.id
                # Link org to pool
                await conn.execute(text("""
                    UPDATE organizations 
                    SET pool_id = :pool_id, updated_at = NOW()
                    WHERE id = :org_id
                """), {'pool_id': pool_id, 'org_id': org_id})
                print(f"   ✅ Root pool created: ID={pool_id}")
            
            await conn.commit()
            
            # Step 5: Verify complete data consistency
            print(f"\n{'='*80}")
            print("VERIFICATION")
            print(f"{'='*80}")
            
            verify_result = await conn.execute(text("""
                SELECT 
                    u.email,
                    u.display_name as user_display_name,
                    o.name as org_name,
                    o.currency,
                    e.name as employee_name,
                    CASE 
                        WHEN u.display_name = e.name THEN '✅ MATCH'
                        ELSE '❌ MISMATCH'
                    END as name_consistency
                FROM users u
                JOIN employees e ON e.auth_user_id = u.id
                JOIN organizations o ON o.id = e.organization_id
                WHERE u.email = :email
                  AND e.deleted_at IS NULL
                  AND o.deleted_at IS NULL
            """), {'email': DEMO_EMAIL})
            
            row = verify_result.fetchone()
            
            if row:
                print(f"\nEmail:                  {row.email}")
                print(f"User Display Name:      {row.user_display_name}")
                print(f"Organization Name:      {row.org_name} ({row.currency})")
                print(f"Employee Name:          {row.employee_name} {row.name_consistency}")
                
                if '✅' in row.name_consistency:
                    print(f"\n{'='*80}")
                    print("✅ DEMO DATA SEEDED SUCCESSFULLY - ALL DATA IS CONSISTENT")
                    print(f"{'='*80}")
                    print(f"\nLogin credentials:")
                    print(f"  Email:    {DEMO_EMAIL}")
                    print(f"  Password: {DEMO_PASSWORD}")
                    print(f"{'='*80}\n")
                else:
                    print(f"\n❌ WARNING: Data inconsistency detected! Please verify manually.\n")
            else:
                print('❌ ERROR: Could not verify seeded data!')
    
    except Exception as e:
        print(f'\n❌ ERROR during seeding: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description='Seed demo data with consistent state')
    parser.add_argument('--force', action='store_true', help='Delete existing demo data and re-seed')
    
    args = parser.parse_args()
    
    asyncio.run(seed_demo_data(force=args.force))


if __name__ == "__main__":
    main()
