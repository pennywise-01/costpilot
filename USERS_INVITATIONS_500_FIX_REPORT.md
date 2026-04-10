# Users & Invitations 500 Errors - Fix Report

**Date:** April 9, 2026  
**Severity:** 🔴 **CRITICAL** - Can't load users or send invitations  
**Status:** ✅ **FIXED**

---

## Executive Summary

Two critical 500 errors were blocking user management:
1. **User Invitations** - `IntegrityError: null value in column "created_at" of relation "user_invitations" violates not-null constraint`
2. **Export Jobs** - `IntegrityError: null value in column "created_at" of relation "export_jobs" violates not-null constraint`

**Root Cause:** Database tables were missing server defaults (`NOW()`) for `created_at` and `updated_at` columns. When the application tried to insert records without explicitly setting timestamps, PostgreSQL rejected them with NOT NULL violations.

**Fix:** Migration 021 added `DEFAULT NOW()` to all affected tables and created triggers to auto-update `updated_at` on modifications.

---

## Error Details

### Error 1: User Invitations

```
IntegrityError: null value in column "created_at" of relation "user_invitations" 
violates not-null constraint

DETAIL: Failing row contains (
  9eb8e6f9-4fed-4ef4-8339-bfbf5b8b9b78, 
  hafzan@mypennywisetesting.site, 
  2e8cbf3b-46ba-4833-bc13-42d99ea5a5ac, 
  cb81c868-341c-4d35-bb1d-8a200fcfef0a, 
  ...
  null,  -- created_at is NULL!
  null,  -- updated_at is NULL!
  1
)

[SQL: INSERT INTO user_invitations (
  email, organization_id, invited_by, role_id, token, status, expires_at, 
  accepted_at, id, deleted_at, version_id
) VALUES ($1::VARCHAR, $2::VARCHAR, ..., $9::VARCHAR, $10::TIMESTAMP, $11::INTEGER) 
RETURNING user_invitations.created_at, user_invitations.updated_at]
```

### Error 2: Export Jobs

```
IntegrityError: null value in column "created_at" of relation "export_jobs" 
violates not-null constraint

DETAIL: Failing row contains (
  ccdd3995-6a0e-4698-8faa-e98fa6017750, 
  2e8cbf3b-46ba-4833-bc13-42d99ea5a5ac, 
  null, 
  testing1, 
  resources, 
  csv, 
  ...
  null,  -- created_at is NULL!
  null,  -- updated_at is NULL!
  1
)
```

---

## Root Cause Analysis

### Why This Happened

1. **Models inherit from `BaseModel`** which defines `created_at` and `updated_at` columns
2. **BaseModel uses `TimestampMixin`** which is supposed to add server defaults via `server_default=func.now()`
3. **Migration gap** - When these tables were created, the server defaults were NOT applied to the database columns
4. **Result** - Columns exist and are NOT NULL, but have NO DEFAULT value, causing INSERT failures when timestamps aren't explicitly provided

### Database State Before Fix

```sql
SELECT column_name, column_default, is_nullable 
FROM information_schema.columns 
WHERE table_name='user_invitations' 
  AND column_name IN ('created_at', 'updated_at');

Result:
 column_name | column_default | is_nullable 
-------------+----------------+-------------
 created_at  |                | NO          ← NO DEFAULT!
 updated_at  |                | NO          ← NO DEFAULT!
```

### Expected State (After Fix)

```sql
SELECT column_name, column_default, is_nullable 
FROM information_schema.columns 
WHERE table_name='user_invitations' 
  AND column_name IN ('created_at', 'updated_at');

Result:
 column_name | column_default | is_nullable 
-------------+----------------+-------------
 created_at  | now()          | NO          ← HAS DEFAULT!
 updated_at  | now()          | NO          ← HAS DEFAULT!
```

---

## The Fix (Migration 021)

**File:** `backend/alembic/versions/021_add_timestamp_server_defaults.py`

### Tables Fixed

| Table | created_at | updated_at | Auto-update Trigger |
|-------|-----------|-----------|---------------------|
| `export_jobs` | ✅ DEFAULT NOW() | ✅ DEFAULT NOW() | ✅ trg_export_jobs_updated_at |
| `user_invitations` | ✅ DEFAULT NOW() | ✅ DEFAULT NOW() | ✅ trg_user_invitations_updated_at |
| `user_preferences` | ✅ DEFAULT NOW() | ✅ DEFAULT NOW() | ✅ trg_user_preferences_updated_at |
| `export_templates` | ✅ DEFAULT NOW() | ✅ DEFAULT NOW() | ✅ trg_export_templates_updated_at |
| `scheduled_exports` | ✅ DEFAULT NOW() | ✅ DEFAULT NOW() | ✅ trg_scheduled_exports_updated_at |
| `user_activity_logs` | ✅ DEFAULT NOW() | ❌ (column doesn't exist) | ❌ (not needed) |

### What the Migration Does

For each table with BOTH columns:
1. `ALTER TABLE ... ALTER COLUMN created_at SET DEFAULT NOW()`
2. `ALTER TABLE ... ALTER COLUMN updated_at SET DEFAULT NOW()`
3. Creates auto-update trigger function
4. Drops old trigger (if exists)
5. Creates new trigger to auto-update `updated_at`

For tables with ONLY `created_at`:
1. `ALTER TABLE ... ALTER COLUMN created_at SET DEFAULT NOW()`

---

## Verification

### Before Fix
```
POST /api/v1/organizations/{id}/users/invite → 500 IntegrityError
POST /api/v1/organizations/{id}/exports      → 500 IntegrityError
```

### After Fix
```
POST /api/v1/organizations/{id}/users/invite → 201 Created ✅
POST /api/v1/organizations/{id}/exports      → 201 Created ✅
```

### Database Verification

```sql
-- Check user_invitations table
SELECT column_name, column_default 
FROM information_schema.columns 
WHERE table_name='user_invitations' 
  AND column_name IN ('created_at', 'updated_at');

Result:
 column_name | column_default 
-------------+----------------
 created_at  | now()
 updated_at  | now()

-- Check export_jobs table
SELECT column_name, column_default 
FROM information_schema.columns 
WHERE table_name='export_jobs' 
  AND column_name IN ('created_at', 'updated_at');

Result:
 column_name | column_default 
-------------+----------------
 created_at  | now()
 updated_at  | now()
```

---

## Impact Assessment

### Before Fix
- 🔴 Can't invite new users to organization
- 🔴 Can't create data exports
- 🔴 Can't set up export templates
- 🔴 Can't schedule recurring exports
- 🔴 All user management features broken

### After Fix
- ✅ User invitations work
- ✅ Export jobs create successfully
- ✅ Export templates save correctly
- ✅ Scheduled exports function
- ✅ Timestamps auto-populate on insert
- ✅ `updated_at` auto-updates on modifications

---

## Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `backend/alembic/versions/021_add_timestamp_server_defaults.py` | **CREATED** | Migration to add timestamp defaults |

---

## Prevention

### Migration Checklist

Add to future migration templates:

```markdown
## When Creating New Tables

- [ ] All timestamp columns use `server_default=func.now()`
- [ ] Verify in migration: `column_default='now()'`
- [ ] Test INSERT without explicit timestamps
- [ ] Test UPDATE triggers for `updated_at`
```

### Code Review Checklist

```markdown
## Timestamp Column Review

- [ ] All models inherit from BaseModel with TimestampMixin
- [ ] Migration includes `server_default=func.now()` in column definition
- [ ] Database column has DEFAULT NOW() after migration
- [ ] Test both INSERT and UPDATE operations
```

---

## Migration Execution

```bash
# Run migration
docker exec costpilot-backend-1 alembic upgrade head

# Output:
Fixing export_jobs...
✅ Fixed export_jobs
Fixing user_invitations...
✅ Fixed user_invitations
Fixing user_preferences...
✅ Fixed user_preferences
Fixing export_templates...
✅ Fixed export_templates
Fixing scheduled_exports...
✅ Fixed scheduled_exports
Fixing user_activity_logs (created_at only)...
✅ Fixed user_activity_logs

✅ All table timestamp defaults added successfully!
```

---

**Report prepared by:** Systematic Debugging Process  
**Date:** April 9, 2026  
**Classification:** Critical Bug Fix (Schema Migration Gap)  
**Risk Level:** LOW (backward compatible, no data migration needed)  
**Deployment Status:** ✅ **COMPLETE - ALL 500 ERRORS RESOLVED**
