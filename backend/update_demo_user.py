"""
Update demo user to test@test.com with known password.

This script performs a COMPLETE update of the demo user, including:
- Email address
- Password
- Display name
- Employee name (in employees table)
- Organization name (if it's a demo/test organization)

Usage:
    python update_demo_user.py [--display-name "Name"] [--org-name "OrgName"]
    
Defaults:
    --display-name: "Test User"
    --org-name: "Luminor"
"""
import asyncio
import sys
import argparse

sys.path.insert(0, '/app')

from app.auth.service import hash_password
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def main():
    parser = argparse.ArgumentParser(description='Update demo user with complete data')
    parser.add_argument('--display-name', default='Test User', help='Display name for the user (default: "Test User")')
    parser.add_argument('--org-name', default='Luminor', help='Organization name (default: "Luminor")')
    parser.add_argument('--email', default='test@test.com', help='Email address (default: "test@test.com")')
    parser.add_argument('--password', default='H4fz4n12@#', help='Password (default: "H4fz4n12@#")')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    
    args = parser.parse_args()
    
    db_url = 'postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot'
    engine = create_async_engine(db_url)

    email = args.email
    password = args.password
    display_name = args.display_name
    org_name = args.org_name
    hashed = hash_password(password)

    try:
        async with engine.begin() as conn:
            # Step 0: Check if user exists with old email or already has new email
            print(f"\n{'='*80}")
            print("CHECKING CURRENT STATE")
            print(f"{'='*80}")
            
            check_old = await conn.execute(text("""
                SELECT id, email, display_name FROM users WHERE email = 'demo@costpilot.io' AND deleted_at IS NULL
            """))
            old_user = check_old.fetchone()
            
            check_new = await conn.execute(text("""
                SELECT id, email, display_name FROM users WHERE email = :email AND deleted_at IS NULL
            """), {'email': email})
            new_user = check_new.fetchone()
            
            if old_user:
                user_id = old_user.id
                print(f"✅ Found user with old email: demo@costpilot.io (ID: {user_id})")
                print(f"   Current display_name: {old_user.display_name}")
                
                # Step 1: Update user credentials and display name
                print(f"\n{'='*80}")
                print("UPDATING USER")
                print(f"{'='*80}")
                
                if args.dry_run:
                    print("[DRY RUN] Would update user email, password, and display name")
                else:
                    result = await conn.execute(text("""
                        UPDATE users 
                        SET email = :email, 
                            hashed_password = :pw,
                            display_name = :display_name,
                            updated_at = NOW()
                        WHERE email = 'demo@costpilot.io'
                    """), {'email': email, 'pw': hashed, 'display_name': display_name})
                    print(f'✅ Updated {result.rowcount} user record(s)')
                    
            elif new_user:
                user_id = new_user.id
                print(f"✅ User already has email: {email} (ID: {user_id})")
                print(f"   Current display_name: {new_user.display_name}")
                
                # Update only display name and password
                print(f"\n{'='*80}")
                print("UPDATING USER (display name and password only)")
                print(f"{'='*80}")
                
                if args.dry_run:
                    print("[DRY RUN] Would update user display name and password")
                else:
                    result = await conn.execute(text("""
                        UPDATE users 
                        SET display_name = :display_name,
                            hashed_password = :pw,
                            updated_at = NOW()
                        WHERE email = :email
                    """), {'email': email, 'pw': hashed, 'display_name': display_name})
                    print(f'✅ Updated {result.rowcount} user record(s)')
            else:
                print(f'❌ ERROR: User not found with email demo@costpilot.io or {email}!')
                return
            
            print(f'✅ User confirmed: id={user_id}, email={email}, display_name={display_name}')

            # Step 3: Update employee name to match user display name
            print(f"\n{'='*80}")
            print("UPDATING EMPLOYEE RECORD")
            print(f"{'='*80}")
            
            if args.dry_run:
                print("[DRY RUN] Would execute:")
                print(f"  UPDATE employees SET name='{display_name}' WHERE auth_user_id='{user_id}'")
            else:
                emp_result = await conn.execute(
                    text("""
                        UPDATE employees 
                        SET name = :name,
                            updated_at = NOW()
                        WHERE auth_user_id = :user_id
                          AND deleted_at IS NULL
                    """),
                    {'name': display_name, 'user_id': user_id}
                )
                print(f'✅ Updated {emp_result.rowcount} employee record(s)')

            # Step 4: Update organization name from "Test Organization" to proper name
            print(f"\n{'='*80}")
            print("UPDATING ORGANIZATION")
            print(f"{'='*80}")
            
            if args.dry_run:
                print("[DRY RUN] Would execute:")
                print(f"  UPDATE organizations SET name='{org_name}' WHERE name='Test Organization'")
            else:
                org_result = await conn.execute(
                    text("""
                        UPDATE organizations 
                        SET name = :org_name,
                            updated_at = NOW()
                        WHERE name = 'Test Organization'
                          AND deleted_at IS NULL
                    """),
                    {'org_name': org_name}
                )
                print(f'✅ Updated {org_result.rowcount} organization record(s)')

            # Step 5: Verify complete data consistency
            print(f"\n{'='*80}")
            print("VERIFICATION")
            print(f"{'='*80}")
            
            verify_result = await conn.execute(text("""
                SELECT 
                    u.email,
                    u.display_name as user_display_name,
                    o.name as org_name,
                    e.name as employee_name,
                    CASE 
                        WHEN u.display_name = e.name THEN '✅ MATCH'
                        ELSE '❌ MISMATCH'
                    END as name_consistency,
                    CASE 
                        WHEN o.name = :expected_org THEN '✅ CORRECT'
                        ELSE '❌ INCORRECT (expected: ' || :expected_org || ')'
                    END as org_status
                FROM users u
                JOIN employees e ON e.auth_user_id = u.id
                JOIN organizations o ON o.id = e.organization_id
                WHERE u.email = :email
                  AND e.deleted_at IS NULL
                  AND o.deleted_at IS NULL
            """), {'email': email, 'expected_org': org_name})
            
            row = verify_result.fetchone()
            
            if row:
                print(f"\nEmail:                  {row.email}")
                print(f"User Display Name:      {row.user_display_name}")
                print(f"Organization Name:      {row.org_name} {row.org_status}")
                print(f"Employee Name:          {row.employee_name} {row.name_consistency}")
                
                if '✅' in row.name_consistency and '✅' in row.org_status:
                    print(f"\n{'='*80}")
                    print("✅ ALL UPDATES COMPLETED SUCCESSFULLY - DATA IS CONSISTENT")
                    print(f"{'='*80}\n")
                else:
                    print(f"\n{'='*80}")
                    print("⚠️  WARNING: Some updates may have failed - please verify manually")
                    print(f"{'='*80}\n")
            else:
                print('❌ ERROR: Could not verify user data after update!')

    except Exception as e:
        print(f'\n❌ ERROR during update: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()
    
    print('Done')


if __name__ == '__main__':
    asyncio.run(main())
