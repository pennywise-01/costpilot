# Cache Status 500 Error - Fix Report

**Date:** April 9, 2026  
**Severity:** 🔴 **HIGH** - Dashboard cache endpoint failing  
**Status:** ✅ **FIXED**

---

## Root Cause

**Error:** `TypeError: can't subtract offset-naive and offset-aware datetimes`

**Location:** `backend/app/cost_cache/models.py` line 191 in `get_health_status()`

**What Happened:**
- `utc_now()` returns a **timezone-aware** datetime (with UTC tzinfo)
- `self.last_successful_collection` was stored as **timezone-naive** (no tzinfo) in the database
- Python can't subtract these two different datetime types, causing a TypeError

**Why It Happened:**
The `last_successful_collection` column is defined as `DateTime(timezone=True)`, but somewhere in the code, a timezone-naive datetime was saved to it. When the cache status endpoint tried to calculate hours since last collection, it crashed.

---

## The Fix

**File:** `backend/app/cost_cache/models.py`

**Changes:**
1. Added `timezone` import
2. Updated `is_healthy()` method to handle both timezone-aware and naive datetimes
3. Updated `get_health_status()` method to handle both timezone-aware and naive datetimes

**Before:**
```python
def is_healthy(self) -> bool:
    if not self.last_successful_collection:
        return False
    hours_since = (utc_now() - self.last_successful_collection).total_seconds() / 3600
    return hours_since < 24
```

**After:**
```python
def is_healthy(self) -> bool:
    if not self.last_successful_collection:
        return False
    # Ensure both datetimes are timezone-aware
    last_time = self.last_successful_collection
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=timezone.utc)
    hours_since = (utc_now() - last_time).total_seconds() / 3600
    return hours_since < 24
```

---

## Verification

After the fix:
- ✅ No 500 errors in backend logs
- ✅ Cache status endpoint returns 200 OK
- ✅ Dashboard loads without errors
- ✅ Handles both timezone-aware and naive datetimes gracefully

---

## Impact

**Before Fix:**
- 🔴 `GET /api/v1/organizations/{id}/expenses/cache-status` → 500
- 🔴 Dashboard shows cache error
- 🔴 Users can't see cache health status

**After Fix:**
- ✅ Cache status endpoint returns proper health status
- ✅ Dashboard displays cache information correctly
- ✅ No timezone-related crashes

---

**Fix applied:** April 9, 2026  
**Files modified:** 1 (`backend/app/cost_cache/models.py`)  
**Lines changed:** 10 (added timezone safety checks)
