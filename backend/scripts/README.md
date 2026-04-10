# CostPilot Database Scripts

This directory contains essential scripts for database management, validation, and seeding.

## Scripts Overview

### 1. `validate_data_integrity.py` - Data Integrity Validator

**Purpose:** Validates database consistency and catches common data integrity issues.

**What it checks:**
- ✅ Users with generic display names (demo, test, user, etc.)
- ✅ Organizations with generic names (test, demo, temp, etc.)
- ✅ Employee name consistency with user display names
- ✅ Orphaned employee records (user deleted but employee remains)
- ✅ Organizations without any employees
- ✅ Users without organization membership
- ✅ Duplicate email addresses
- ✅ Database health and table counts

**Usage:**
```bash
# From backend directory
docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py

# Fail with exit code 1 if warnings found
docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py --fail-on-warnings

# Custom database URL
docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py --db-url "postgresql+asyncpg://..."
```

**When to run:**
- Before and after database migrations
- After manual database operations
- As part of CI/CD pipeline (use `--fail-on-warnings`)
- Regular scheduled health checks

**Exit Codes:**
- `0` - No issues found
- `1` - Warnings or errors found (with `--fail-on-warnings`)
- `2` - Script execution failed

---

### 2. `seed_demo_data.py` - Demo Data Seeder

**Purpose:** Creates a complete, consistent demo organization with proper naming.

**What it creates:**
- User: `demo@costpilot.io` with display name "Demo Administrator"
- Organization: "Acme Corporation" (marked as demo)
- Employee record linking user to organization
- Root pool for the organization
- Default RBAC roles

**Usage:**
```bash
# Seed demo data (won't create if exists)
docker exec costpilot-backend-1 python /app/scripts/seed_demo_data.py

# Force re-seed (deletes existing demo data first)
docker exec costpilot-backend-1 python /app/scripts/seed_demo_data.py --force
```

**When to use:**
- Initial development setup
- Resetting demo environment
- Testing organization features

**Idempotent:** The script checks if data exists before creating. Use `--force` to recreate.

---

### 3. `update_demo_user.py` - Demo User Update Script

**Purpose:** Updates the demo user credentials and ensures data consistency across all related tables.

**What it updates:**
- User email (from `demo@costpilot.io` to custom email)
- User password
- User display name
- Employee name (automatically synced)
- Organization name (from "Test Organization" to custom name)

**Usage:**
```bash
# Update with defaults
docker exec costpilot-backend-1 python /app/update_demo_user.py

# Custom values
docker exec costpilot-backend-1 python /app/update_demo_user.py \
  --email "admin@example.com" \
  --password "SecurePass123!" \
  --display-name "John Doe" \
  --org-name "Acme Corp"

# Dry run (shows what would be updated)
docker exec costpilot-backend-1 python /app/update_demo_user.py --dry-run
```

**When to use:**
- Converting demo user to test user
- Updating test credentials
- Fixing data consistency issues

**Important:** This script handles ALL related fields to prevent partial updates.

---

## Database Trigger (Migration 019)

A PostgreSQL trigger automatically keeps employee names in sync with user display names.

**How it works:**
- When `users.display_name` is updated
- The trigger fires automatically
- All non-deleted `employees.name` records for that user are updated
- This ensures consistency without application-level logic

**Trigger Details:**
- Function: `sync_employee_name_with_user()`
- Trigger: `trg_sync_employee_name_with_user`
- Table: `users` (AFTER UPDATE OF display_name)
- Migration: `019_add_employee_name_sync_trigger.py`

**Test the trigger:**
```sql
-- Update user display name
UPDATE users SET display_name = 'New Name' WHERE email = 'test@test.com';

-- Verify employee name was automatically updated
SELECT name FROM employees WHERE auth_user_id = (SELECT id FROM users WHERE email = 'test@test.com');
-- Result: 'New Name' (automatically synced)
```

---

## Best Practices

### 1. Before Manual Database Operations

```bash
# 1. Run validation to capture current state
docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py > before_validation.txt

# 2. Perform your operation
# ... (your SQL or script)

# 3. Run validation again to verify consistency
docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py > after_validation.txt

# 4. Compare results
diff before_validation.txt after_validation.txt
```

### 2. Creating New Users/Organizations

**DO:**
- Use application APIs when possible (POST /api/v1/register, POST /api/v1/organizations)
- Ensure display names are meaningful (not "test", "demo", "user")
- Use the validation script after manual operations

**DON'T:**
- Perform partial updates (update email but forget display_name)
- Use generic names that will trigger validation warnings
- Skip validation after database changes

### 3. Database Migrations

```bash
# Always run migrations before validation
docker exec costpilot-backend-1 alembic upgrade head

# Then validate
docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py
```

### 4. CI/CD Integration

Add to your deployment pipeline:

```yaml
# Example GitHub Actions step
- name: Validate Database Integrity
  run: |
    docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py --fail-on-warnings
  if: success()
```

---

## Troubleshooting

### Validation Warnings

**"Found X user(s) with generic display names"**
- Update the user with a meaningful name
- Use `update_demo_user.py` or direct SQL:
  ```sql
  UPDATE users SET display_name = 'John Doe' WHERE email = 'test@test.com';
  ```

**"Found X employee record(s) where name doesn't match user"**
- The trigger should handle this automatically for new updates
- For existing mismatches, manually sync:
  ```sql
  UPDATE employees e SET name = u.display_name
  FROM users u WHERE e.auth_user_id = u.id AND e.deleted_at IS NULL;
  ```

### Script Errors

**"Can't operate on closed transaction"**
- This happens if you modified the scripts and added `commit()` calls
- The scripts use `engine.begin()` context manager which auto-commits
- Don't call `commit()` inside the context manager

**"User not found with email..."**
- The script looks for `demo@costpilot.io` or the target email
- If the user has a different email, update it manually or use a different script

---

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| `update_demo_user.py` | `backend/update_demo_user.py` | Update demo user credentials |
| `validate_data_integrity.py` | `backend/scripts/validate_data_integrity.py` | Data validation |
| `seed_demo_data.py` | `backend/scripts/seed_demo_data.py` | Demo data seeding |
| `019_add_employee_name_sync_trigger.py` | `backend/alembic/versions/019_...` | Migration for trigger |

---

## Security Notes

- ⚠️ **Never commit passwords** in scripts or documentation
- ⚠️ The `update_demo_user.py` script has a default password - change it in production
- ⚠️ Validation scripts should not be run with production credentials in public CI
- ✅ All scripts use parameterized queries (no SQL injection risk)
- ✅ Scripts check for soft-deletes (won't affect deleted records)

---

**Last Updated:** April 9, 2026  
**Migration Version:** 019  
**Scripts Version:** 1.0.0
