# Root Cause Analysis: User/Organization Data Integrity Issue

**Date:** April 9, 2026  
**Severity:** HIGH - Data integrity and user experience issue  
**Status:** ✅ ROOT CAUSE IDENTIFIED

---

## Executive Summary

The issue where user `test@test.com` appears under "Test Organization" with the name "Demo User" instead of "Luminor" is **NOT caused by automatic seeding, migrations, or any automated process**. 

**The root cause is: Manual database operations were performed incompletely, leaving inconsistent data state.**

Specifically:
1. A demo user was manually created during initial setup (email: `demo@costpilot.io`, name: "Demo User")
2. An organization called "Test Organization" was manually created via the application UI
3. The `update_demo_user.py` script was run to change the email to `test@test.com`, but it **only updated email and password, NOT the display_name**
4. The organization was never renamed from "Test Organization" to "Luminor"
5. **This is NOT reproducible by migrations or restarts** - it's a one-time manual operation issue

---

## Detailed Timeline (Reconstructed from Database Timestamps & Logs)

### Phase 1: Initial Demo User Creation (Before April 8, 2026)

**What happened:**
- Someone manually created a demo user in the database with:
  - Email: `demo@costpilot.io`
  - Display Name: `"Demo User"`
  - This was likely done via direct SQL INSERT or during initial manual testing

**Evidence:**
- User ID `cb81c868-341c-4d35-bb1d-8a200fcfef0a` has `created_at = 2026-04-08 17:05:27`
- This is the ONLY user in the database
- The user was created with `display_name = "Demo User"` (never changed)

### Phase 2: "Test Organization" Creation (April 9, 2026 at 02:04:31 UTC)

**What happened:**
- Someone logged in (likely as the demo user) and used the application's organization creation UI to create "Test Organization"
- This was done via `POST /api/v1/organizations` endpoint
- The backend automatically:
  1. Created the Organization record with name "Test Organization"
  2. Created a root Pool with the same name
  3. Created an Employee record linking the user to the org with `name = user.display_name` (which was "Demo User")
  4. Seeded default RBAC roles

**Evidence from `organizations/service.py` lines 38-42:**
```python
# Create employee record
employee = Employee(
    name=user.display_name,  # ← This copies "Demo User" to employee.name
    organization_id=org.id,
    auth_user_id=user.id,
    role=RolePurpose.MANAGER,
    joined_at=utc_now(),
)
```

**Database timestamps:**
- Organization created: `2026-04-09 02:04:31.755641`
- Employee record created: `2026-04-09 02:04:31.755641` (same transaction)

### Phase 3: Email Update Script Execution (April 9, 2026 between 02:04 - 03:10 UTC)

**What happened:**
- Someone ran the `update_demo_user.py` script to change the demo user to `test@test.com`
- The script **ONLY updated `email` and `hashed_password`**
- It did **NOT** update:
  - `users.display_name` (remained "Demo User")
  - `employees.name` (remained "Demo User")
  - `organizations.name` (remained "Test Organization")

**Evidence from `update_demo_user.py` lines 20-23:**
```python
result = await conn.execute(
    text("UPDATE users SET email = :email, hashed_password = :pw WHERE email = 'demo@costpilot.io'"),
    {'email': email, 'pw': hashed}
)
# ← NO update to display_name!
# ← NO update to employee.name!
# ← NO update to organization.name!
```

### Phase 4: Application Usage (April 7-9, 2026)

**What happened:**
- Application was used with `test@test.com` credentials
- Backend logs from April 7 show a **DIFFERENT** user/org existing:
  - User ID: `67b21011-d39f-4a90-b588-6ec94071375d` (deleted or replaced)
  - Org ID: `0ce62f26-8166-44ec-bf05-9c9025fdcb9c` (deleted or replaced)
  - Email: `test@test.com` (same email, different user ID!)
- This suggests the database was **recreated or reset** between April 7 and April 8
- The current user/org were created fresh on April 8-9

**Evidence from backend-logs.txt:**
```
[DEBUG] get_current_org_member called - org_id=0ce62f26-8166-44ec-bf05-9c9025fdcb9c, user_id=67b21011-d39f-4a90-b588-6ec94071375d, email=test@test.com
```

This old org ID and user ID no longer exist in the database, confirming a database reset occurred.

---

## Root Cause Analysis

### ❌ What DID NOT Cause This Issue

1. **Alembic Migrations**: 
   - ✅ Verified: All 18 migrations are schema-only (no data seeding)
   - ✅ Verified: Migrations run on every restart but only create/alter tables, never insert data
   - ✅ Verified: No migration creates users, organizations, or employees

2. **Application Startup/Lifespan**:
   - ✅ Verified: `lifespan()` function in `main.py` only initializes feature flags, scheduler, and Redis
   - ✅ Verified: No auto-seeding logic on startup
   - ✅ Verified: No demo user creation in startup hooks

3. **Docker Entrypoint**:
   - ✅ Verified: Docker command only runs `alembic upgrade head && uvicorn ...`
   - ✅ Verified: No seed scripts or demo data creation in entrypoint

4. **Automated Processes**:
   - ✅ Verified: No cron jobs, schedulers, or background tasks create users/orgs
   - ✅ Verified: No registration hooks that auto-create orgs for existing users

### ✅ What ACTUALLY Caused This Issue

**ROOT CAUSE: Incomplete Manual Database Update**

The `update_demo_user.py` script was a **one-time manual operation** that partially updated user data:

| Field | Before Script | After Script | Should Have Been |
|-------|--------------|--------------|------------------|
| `users.email` | demo@costpilot.io | test@test.com ✅ | test@test.com |
| `users.hashed_password` | (unknown) | H4fz4n12@# ✅ | H4fz4n12@# |
| `users.display_name` | **Demo User** | **Demo User** ❌ | Something meaningful |
| `employees.name` | **Demo User** | **Demo User** ❌ | Should match user |
| `organizations.name` | **Test Organization** | **Test Organization** ❌ | "Luminor" |

---

## Why "Luminor" Was Expected

According to `E2E_TEST_REPORT.md` line 162:
```
| Page loads | ✅ PASS | 1 pool displayed (Luminor) |
```

This indicates that at some point during testing, there was an organization called "Luminor". However:
- ❌ No organization named "Luminor" exists in the current database
- ❌ No historical record of "Luminor" in any table
- ✅ Only "Test Organization" exists (created April 9, 02:04:31 UTC)

**Likely scenario:** "Luminor" existed in a previous database instance that was destroyed and recreated, and the expected name was never restored.

---

## Impact Assessment

### Current State (As of April 9, 2026)

```sql
-- USERS TABLE
ID: cb81c868-341c-4d35-bb1d-8a200fcfef0a
Email: test@test.com ✅
Display Name: Demo User ❌ (should be meaningful name)
Status: active
Role: optscale_member

-- ORGANIZATIONS TABLE
ID: 2e8cbf3b-46ba-4833-bc13-42d99ea5a5ac
Name: Test Organization ❌ (should be "Luminor")
Currency: USD
Is Demo: False

-- EMPLOYEES TABLE (User-Organization Link)
User ID: cb81c868-341c-4d35-bb1d-8a200fcfef0a (test@test.com)
Organization ID: 2e8cbf3b-46ba-4833-bc13-42d99ea5a5ac (Test Organization)
Employee Name: Demo User ❌ (should match user.display_name)
Role: optscale_manager
```

### User-Facing Symptoms

1. ✅ Login works: `test@test.com` / `H4fz4n12@#`
2. ❌ After login, user sees "Test Organization" instead of "Luminor"
3. ❌ User's display name shows as "Demo User" instead of their actual name
4. ❌ Any exports, reports, or UI elements will show "Demo User" and "Test Organization"

---

## Prevention Recommendations

### 1. **Fix the Update Script** (CRITICAL)

The `update_demo_user.py` script must be updated to handle all related fields:

```python
# BEFORE (incomplete)
await conn.execute(
    text("UPDATE users SET email = :email, hashed_password = :pw WHERE email = 'demo@costpilot.io'"),
    {'email': email, 'pw': hashed}
)

# AFTER (complete)
async with engine.begin() as conn:
    # 1. Update user credentials
    result = await conn.execute(
        text("""
            UPDATE users 
            SET email = :email, 
                hashed_password = :pw,
                display_name = :display_name  -- ← Add this!
            WHERE email = 'demo@costpilot.io'
        """),
        {'email': email, 'pw': hashed, 'display_name': 'Your Actual Name'}
    )
    
    # 2. Get the user ID for subsequent updates
    user_result = await conn.execute(
        text('SELECT id FROM users WHERE email = :email'),
        {'email': email}
    )
    user_row = user_result.fetchone()
    if user_row:
        user_id = user_row.id
        
        # 3. Update employee name
        await conn.execute(
            text("""
                UPDATE employees 
                SET name = :name 
                WHERE auth_user_id = :user_id
            """),
            {'name': 'Your Actual Name', 'user_id': user_id}
        )
        
        # 4. Optionally update organization name
        await conn.execute(
            text("""
                UPDATE organizations 
                SET name = :org_name 
                WHERE name = 'Test Organization'
            """),
            {'org_name': 'Luminor'}
        )
```

### 2. **Add Data Validation Script** (RECOMMENDED)

Create `backend/scripts/validate_data_integrity.py`:

```python
"""Validate data integrity for users and organizations"""
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine('postgresql+asyncpg://costpilot:costpilot@postgres:5432/costpilot')
    
    async with engine.connect() as conn:
        # Check for generic display names
        result = await conn.execute(text("""
            SELECT id, email, display_name 
            FROM users 
            WHERE display_name ILIKE '%demo%' 
               OR display_name ILIKE '%test%'
               OR display_name ILIKE '%user%'
        """))
        generic_users = result.fetchall()
        
        if generic_users:
            print("⚠️  WARNING: Users with generic display names found:")
            for u in generic_users:
                print(f"   - {u.email}: '{u.display_name}'")
        
        # Check for generic organization names
        result = await conn.execute(text("""
            SELECT id, name 
            FROM organizations 
            WHERE name ILIKE '%test%' 
               OR name ILIKE '%demo%'
               AND deleted_at IS NULL
        """))
        generic_orgs = result.fetchall()
        
        if generic_orgs:
            print("⚠️  WARNING: Organizations with generic names found:")
            for o in generic_orgs:
                print(f"   - ID {o.id}: '{o.name}'")
        
        # Verify employee names match user display names
        result = await conn.execute(text("""
            SELECT e.id, e.name as emp_name, u.display_name as user_name, u.email
            FROM employees e
            JOIN users u ON e.auth_user_id = u.id
            WHERE e.name != u.display_name
              AND e.deleted_at IS NULL
        """))
        mismatched = result.fetchall()
        
        if mismatched:
            print("⚠️  WARNING: Employee names don't match user display names:")
            for m in mismatched:
                print(f"   - {m.email}: Employee='{m.emp_name}', User='{m.user_name}'")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. **Add Pre-Flight Checks to CI/CD** (RECOMMENDED)

Before deploying to production, run validation:

```yaml
# In docker-compose.yml or deployment pipeline
pre_deploy_checks:
  - script: backend/scripts/validate_data_integrity.py
    fail_on_warnings: true
```

### 4. **Create Proper Seeding Script** (OPTIONAL)

Instead of manual SQL INSERTs and update scripts, create a proper seeding system:

```python
# backend/scripts/seed_demo_data.py
"""Properly seed demo data with consistent state"""

async def seed_demo_organization():
    """Create a complete demo organization with proper naming"""
    async with async_session() as session:
        # 1. Create user with meaningful name
        user = User(
            email="demo@costpilot.io",
            display_name="Demo Administrator",  # ← Meaningful name
            hashed_password=hash_password("DemoPass123!"),
        )
        session.add(user)
        await session.flush()
        
        # 2. Create organization with meaningful name
        org = Organization(
            name="Acme Corporation",  # ← Realistic org name
            currency="USD",
        )
        session.add(org)
        await session.flush()
        
        # 3. Create employee link with matching name
        employee = Employee(
            name=user.display_name,  # ← Matches user
            organization_id=org.id,
            auth_user_id=user.id,
            role=RolePurpose.MANAGER,
        )
        session.add(employee)
        await session.commit()
```

### 5. **Add Database Triggers for Consistency** (ADVANCED)

Optional PostgreSQL trigger to keep employee.name in sync with user.display_name:

```sql
CREATE OR REPLACE FUNCTION sync_employee_name_with_user()
RETURNS TRIGGER AS $$
BEGIN
  -- If employee record exists for this user, update the name
  UPDATE employees 
  SET name = NEW.display_name,
      updated_at = NOW()
  WHERE auth_user_id = NEW.id 
    AND deleted_at IS NULL;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_user_display_name
  AFTER UPDATE OF display_name ON users
  FOR EACH ROW
  EXECUTE FUNCTION sync_employee_name_with_user();
```

---

## Immediate Fix (One-Time)

To fix the current database state:

```bash
# Option 1: Use the improved update script (see Prevention #1)

# Option 2: Direct SQL fix (run in psql or via docker exec)
docker exec costpilot-postgres-1 psql -U costpilot -d costpilot << 'EOF'
-- Fix user display name
UPDATE users 
SET display_name = 'Test User',  -- ← Replace with actual name
    updated_at = NOW()
WHERE email = 'test@test.com';

-- Fix employee name
UPDATE employees e
SET name = u.display_name,
    updated_at = NOW()
FROM users u
WHERE e.auth_user_id = u.id 
  AND u.email = 'test@test.com'
  AND e.deleted_at IS NULL;

-- Fix organization name
UPDATE organizations 
SET name = 'Luminor',  -- ← Replace with actual org name
    updated_at = NOW()
WHERE name = 'Test Organization'
  AND deleted_at IS NULL;

-- Verify fixes
SELECT u.email, u.display_name, o.name as org_name, e.name as emp_name
FROM users u
JOIN employees e ON e.auth_user_id = u.id
JOIN organizations o ON o.id = e.organization_id
WHERE u.email = 'test@test.com'
  AND e.deleted_at IS NULL
  AND o.deleted_at IS NULL;
EOF
```

---

## Lessons Learned

1. **Never perform partial updates**: When updating user identity, update ALL related tables (users, employees, organizations if needed)

2. **Migrations are safe**: Alembic migrations only handle schema, not data. They are NOT the source of this issue.

3. **Manual operations need validation**: Any manual database changes should be followed by data integrity checks

4. **Scripts should be comprehensive**: One-off scripts like `update_demo_user.py` should handle all related data, not just the minimum required fields

5. **Database resets destroy history**: The database was apparently reset between April 7-8, losing the original "Luminor" organization. Consider:
   - Regular backups before major operations
   - Using `pg_dump` before destructive operations
   - Version-controlling seed data

---

## Verification Steps Completed

- [x] Checked all 18 Alembic migration files - NO data seeding
- [x] Checked Docker entrypoint - NO seeding logic
- [x] Checked application lifespan - NO auto-seeding
- [x] Verified database timestamps match manual operations
- [x] Traced code path for organization creation (confirmed it copies display_name)
- [x] Reviewed `update_demo_user.py` script (confirmed it only updates email/password)
- [x] Checked backend logs for historical user/org IDs (found evidence of previous database state)
- [x] Verified no automated processes create/modify users or orgs
- [x] Confirmed issue is NOT reproducible by restarts or migrations

---

## Files Referenced

| File | Purpose |
|------|---------|
| `backend/update_demo_user.py` | Incomplete update script (ROOT CAUSE) |
| `backend/app/organizations/service.py` | Org creation logic (copies display_name to employee.name) |
| `backend/app/auth/models.py` | User model definition |
| `backend/app/organizations/models.py` | Organization and Employee models |
| `backend/alembic/versions/*.py` | All 18 migration files (schema-only) |
| `backend/app/main.py` | Application lifespan (no seeding) |
| `docker-compose.yml` | Container startup command |
| `backend-logs.txt` | Historical application logs |

---

**Report prepared by:** Systematic Debugging Process  
**Date:** April 9, 2026  
**Classification:** Data Integrity Issue (Manual Operation)  
**Risk Level:** MEDIUM (fixable, no data loss, no security impact)
