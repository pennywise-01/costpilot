"""
Data Integrity Validation Script

Checks for common data integrity issues in the CostPilot database:
- Users with generic/display names (demo, test, user, etc.)
- Organizations with generic names (test, demo, temp, etc.)
- Employee names that don't match user display names
- Orphaned employee records (user deleted but employee remains)
- Orphaned organization references
- Users without any organization membership
- Organizations without any employees

Usage:
    python scripts/validate_data_integrity.py [--fail-on-warnings]
    
Returns exit code 1 if issues found and --fail-on-warnings is set.
"""
import asyncio
import sys
import argparse

sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


class ValidationResult:
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.info = []
    
    def add_warning(self, message):
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")
    
    def add_error(self, message):
        self.errors.append(message)
        print(f"❌ ERROR: {message}")
    
    def add_info(self, message):
        self.info.append(message)
        print(f"ℹ️  {message}")
    
    @property
    def has_issues(self):
        return len(self.warnings) > 0 or len(self.errors) > 0
    
    def print_summary(self):
        print(f"\n{'='*80}")
        print("VALIDATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total Warnings: {len(self.warnings)}")
        print(f"Total Errors:   {len(self.errors)}")
        print(f"Total Info:     {len(self.info)}")
        
        if not self.has_issues:
            print(f"\n✅ No data integrity issues found!")
        else:
            if self.errors:
                print(f"\n❌ {len(self.errors)} critical error(s) require immediate attention!")
            if self.warnings:
                print(f"\n⚠️  {len(self.warnings)} warning(s) should be reviewed")
        
        print(f"{'='*80}\n")


async def validate_generic_user_names(engine, result):
    """Check for users with generic/display names like 'demo', 'test', 'user', etc."""
    print(f"\n{'='*80}")
    print("CHECK 1: Generic User Display Names")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        sql_result = await conn.execute(text("""
            SELECT id, email, display_name, created_at
            FROM users
            WHERE (display_name ILIKE '%demo%' 
               OR display_name ILIKE '%test%'
               OR display_name ILIKE '%user%'
               OR display_name ILIKE '%admin%'
               OR display_name ILIKE '%temp%'
               OR display_name ILIKE '%placeholder%'
               OR display_name = '')
              AND deleted_at IS NULL
            ORDER BY created_at DESC
        """))
        generic_users = sql_result.fetchall()
        
        if generic_users:
            result.add_warning(f"Found {len(generic_users)} user(s) with generic display names:")
            for u in generic_users:
                print(f"   - {u.email}: '{u.display_name}' (created: {u.created_at})")
        else:
            result.add_info("All users have meaningful display names")


async def validate_generic_organization_names(engine, result):
    """Check for organizations with generic names."""
    print(f"\n{'='*80}")
    print("CHECK 2: Generic Organization Names")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        sql_result = await conn.execute(text("""
            SELECT id, name, created_at, is_demo
            FROM organizations
            WHERE (name ILIKE '%test%' 
               OR name ILIKE '%demo%'
               OR name ILIKE '%temp%'
               OR name ILIKE '%placeholder%'
               OR name ILIKE '%sample%'
               OR name = '')
              AND deleted_at IS NULL
            ORDER BY created_at DESC
        """))
        generic_orgs = sql_result.fetchall()
        
        if generic_orgs:
            result.add_warning(f"Found {len(generic_orgs)} organization(s) with generic names:")
            for o in generic_orgs:
                demo_flag = " [DEMO]" if o.is_demo else ""
                print(f"   - ID {o.id}: '{o.name}'{demo_flag} (created: {o.created_at})")
        else:
            result.add_info("All organizations have meaningful names")


async def validate_employee_user_name_consistency(engine, result):
    """Check that employee.name matches user.display_name."""
    print(f"\n{'='*80}")
    print("CHECK 3: Employee Name vs User Display Name Consistency")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        sql_result = await conn.execute(text("""
            SELECT 
                e.id as employee_id,
                e.name as employee_name,
                u.id as user_id,
                u.email,
                u.display_name as user_display_name,
                o.name as org_name
            FROM employees e
            JOIN users u ON e.auth_user_id = u.id
            JOIN organizations o ON e.organization_id = o.id
            WHERE e.name != u.display_name
              AND e.deleted_at IS NULL
              AND u.deleted_at IS NULL
              AND o.deleted_at IS NULL
            ORDER BY u.email
        """))
        mismatched = sql_result.fetchall()
        
        if mismatched:
            result.add_error(f"Found {len(mismatched)} employee record(s) where name doesn't match user display name:")
            for m in mismatched:
                print(f"   - {m.email} in '{m.org_name}'")
                print(f"     Employee Name: '{m.employee_name}'")
                print(f"     User Name:     '{m.user_display_name}'")
                print(f"     → Should be:   '{m.user_display_name}'")
        else:
            result.add_info("All employee names match their user display names")


async def validate_orphaned_employees(engine, result):
    """Check for employee records where the user has been deleted."""
    print(f"\n{'='*80}")
    print("CHECK 4: Orphaned Employee Records (Deleted Users)")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        sql_result = await conn.execute(text("""
            SELECT 
                e.id as employee_id,
                e.name as employee_name,
                e.auth_user_id as user_id,
                o.name as org_name,
                e.created_at
            FROM employees e
            LEFT JOIN users u ON e.auth_user_id = u.id
            JOIN organizations o ON e.organization_id = o.id
            WHERE u.id IS NULL
              AND e.deleted_at IS NULL
            ORDER BY e.created_at
        """))
        orphans = sql_result.fetchall()
        
        if orphans:
            result.add_error(f"Found {len(orphans)} orphaned employee record(s) (user deleted):")
            for o in orphans:
                print(f"   - Employee '{o.employee_name}' (ID: {o.employee_id})")
                print(f"     References deleted user ID: {o.user_id}")
                print(f"     Organization: '{o.org_name}'")
        else:
            result.add_info("No orphaned employee records found")


async def validate_orphaned_organizations(engine, result):
    """Check for organizations with no employees."""
    print(f"\n{'='*80}")
    print("CHECK 5: Organizations Without Employees")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        sql_result = await conn.execute(text("""
            SELECT 
                o.id,
                o.name,
                o.created_at,
                o.is_demo,
                COUNT(e.id) as employee_count
            FROM organizations o
            LEFT JOIN employees e ON o.id = e.organization_id AND e.deleted_at IS NULL
            WHERE o.deleted_at IS NULL
            GROUP BY o.id, o.name, o.created_at, o.is_demo
            HAVING COUNT(e.id) = 0
            ORDER BY o.created_at
        """))
        empty_orgs = sql_result.fetchall()
        
        if empty_orgs:
            result.add_warning(f"Found {len(empty_orgs)} organization(s) with no employees:")
            for o in empty_orgs:
                demo_flag = " [DEMO]" if o.is_demo else ""
                print(f"   - '{o.name}'{demo_flag} (created: {o.created_at})")
        else:
            result.add_info("All organizations have at least one employee")


async def validate_users_without_organization(engine, result):
    """Check for users who are not members of any organization."""
    print(f"\n{'='*80}")
    print("CHECK 6: Users Without Organization Membership")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        sql_result = await conn.execute(text("""
            SELECT 
                u.id,
                u.email,
                u.display_name,
                u.created_at,
                u.is_active
            FROM users u
            LEFT JOIN employees e ON u.id = e.auth_user_id AND e.deleted_at IS NULL
            WHERE e.id IS NULL
              AND u.deleted_at IS NULL
            ORDER BY u.created_at
        """))
        unassigned_users = sql_result.fetchall()
        
        if unassigned_users:
            result.add_warning(f"Found {len(unassigned_users)} active user(s) not in any organization:")
            for u in unassigned_users:
                active_status = " [ACTIVE]" if u.is_active else " [INACTIVE]"
                print(f"   - {u.email} ('{u.display_name}'){active_status} (created: {u.created_at})")
        else:
            result.add_info("All active users belong to at least one organization")


async def validate_duplicate_emails(engine, result):
    """Check for duplicate email addresses (should be unique but verify)."""
    print(f"\n{'='*80}")
    print("CHECK 7: Duplicate Email Addresses")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        sql_result = await conn.execute(text("""
            SELECT email, COUNT(*) as count
            FROM users
            WHERE deleted_at IS NULL
            GROUP BY email
            HAVING COUNT(*) > 1
            ORDER BY email
        """))
        duplicates = sql_result.fetchall()
        
        if duplicates:
            result.add_error(f"Found {len(duplicates)} duplicate email address(es):")
            for d in duplicates:
                print(f"   - '{d.email}' appears {d.count} times")
        else:
            result.add_info("No duplicate email addresses found")


async def validate_database_health(engine, result):
    """Basic database health checks."""
    print(f"\n{'='*80}")
    print("CHECK 8: Database Health")
    print(f"{'='*80}")
    
    async with engine.connect() as conn:
        try:
            sql_result = await conn.execute(text("SELECT 1"))
            sql_result.scalar()  # Removed await - scalar() doesn't return awaitable
            result.add_info("Database connection: ✅ Healthy")
        except Exception as e:
            result.add_error(f"Database connection: ❌ Failed - {e}")
            return
        
        # Check table counts
        tables = {
            'users': 'SELECT COUNT(*) FROM users WHERE deleted_at IS NULL',
            'organizations': 'SELECT COUNT(*) FROM organizations WHERE deleted_at IS NULL',
            'employees': 'SELECT COUNT(*) FROM employees WHERE deleted_at IS NULL',
        }
        
        for table_name, query in tables.items():
            sql_result = await conn.execute(text(query))
            count = sql_result.scalar()
            result.add_info(f"{table_name}: {count} active record(s)")


async def main():
    parser = argparse.ArgumentParser(description='Validate CostPilot database data integrity')
    parser.add_argument('--fail-on-warnings', action='store_true', 
                       help='Exit with code 1 if any warnings or errors found')
    parser.add_argument('--db-url', default='postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot',
                       help='Database URL (default: postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print("COSTPILOT DATABASE INTEGRITY VALIDATION")
    print(f"{'='*80}\n")
    
    engine = create_async_engine(args.db_url)
    result = ValidationResult()
    
    try:
        # Run all validation checks
        await validate_database_health(engine, result)
        await validate_generic_user_names(engine, result)
        await validate_generic_organization_names(engine, result)
        await validate_employee_user_name_consistency(engine, result)
        await validate_orphaned_employees(engine, result)
        await validate_orphaned_organizations(engine, result)
        await validate_users_without_organization(engine, result)
        await validate_duplicate_emails(engine, result)
        
        # Print summary
        result.print_summary()
        
        # Exit with appropriate code
        if args.fail_on_warnings and result.has_issues:
            print("Exiting with code 1 due to --fail-on-warnings flag\n")
            sys.exit(1)
        elif result.errors:
            print("Exiting with code 1 due to critical errors\n")
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
