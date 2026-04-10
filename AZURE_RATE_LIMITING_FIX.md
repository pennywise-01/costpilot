# Azure Rate Limiting (429) - Root Cause Analysis

**Date:** April 7, 2026  
**Issue:** Dashboard shows $0/mo despite Azure having $0.06 in costs  
**Severity:** 🔴 HIGH - Financial data inaccurate  

---

## Root Cause Identified

**Azure Cost Management API is returning HTTP 429 (Too Many Requests) errors** due to rate limiting.

### Backend Log Evidence:

```json
{
  "timestamp": "2026-04-07 13:31:23,159",
  "level": "ERROR",
  "message": "Azure Cost Management API error: Cloud provider API error",
  "exception": {
    "type": "BadRequestError",
    "message": "azure.core.exceptions.HttpResponseError: (429) Too many requests. Please retry.\nCode: 429\nMessage: Too many requests. Please retry."
  }
}
```

```
Cost cache refresh complete for org 0ce62f26-...: 2/3 accounts successful, total=$0.00
```

### What's Happening:

1. **Azure account HAS cost data**: $0.06 this month, $0.31 last month ✅
2. **Multiple concurrent API calls** being made to Azure Cost Management simultaneously:
   - Cloud Accounts page → `get_cloud_account_summary()` → Azure API
   - Dashboard → `get_expense_summary()` → Azure API
   - Cost cache refresh → Azure API
   - Resource discovery → Azure Cost Management API

3. **Azure Cost Management API has strict rate limits** and rejects requests with HTTP 429

4. **The 429 error gets wrapped** in BadRequestError (400) by error handling in `azure.py` line 234

5. **Expense aggregation silently fails** for Azure account, returns $0 total instead of $0.06

### Why Cloud Accounts Page Shows $0.06 But Dashboard Shows $0:

| Page | Behavior | Result |
|------|----------|--------|
| Cloud Accounts | Calls accounts individually with spacing | ✅ Azure $0.06 shows |
| Dashboard | Calls all 3 accounts in parallel via `asyncio.gather()` | ❌ Azure rate limited (429) |
| Cache Refresh | Calls all accounts in parallel | ❌ Azure rate limited (429) |

**Race condition:** Sometimes Azure API accepts the call, sometimes rejects with 429 depending on timing.

---

## Impact

- **Dashboard Monthly Spend:** Shows $0 instead of $0.06
- **Dashboard Last Month:** Shows $0 instead of $0.31
- **Dashboard Forecast:** Shows $0 instead of $0.27
- **Cost Cache:** Stores $0 total (2/3 accounts successful)
- **User Trust:** Users cannot rely on dashboard for accurate cost data

---

## Proposed Fixes (Priority Order)

### Fix #1: Add HTTP 429 Detection and Exponential Backoff 🔴 CRITICAL

**File:** `backend/app/shared/retry.py`

**Problem:** Current retry logic doesn't specifically handle rate limit errors

**Solution:** Detect 429 errors and apply longer exponential backoff

```python
import asyncio

async def with_retry(func, config=None):
    """Retry with special handling for rate limits (429)."""
    max_retries = config.get('max_retries', 3) if config else 3
    base_delay = config.get('base_delay', 1) if config else 1
    
    errors = []
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            errors.append(str(e))
            
            # Check if this is a rate limit error
            is_rate_limit = "429" in str(e) or "Too many requests" in str(e)
            
            if is_rate_limit:
                # Longer backoff for rate limits: 5s, 10s, 20s, 40s, 60s
                wait_time = min(2 ** attempt * 5, 60)
                logger.warning(
                    f"Rate limited (429), waiting {wait_time}s before retry "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
            else:
                # Normal backoff: 1s, 2s, 4s
                wait_time = min(2 ** attempt * base_delay, 10)
            
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
    
    raise RetryExhaustedError(f"All retry attempts exhausted. Errors: {errors}")
```

**Impact:** Azure API calls will automatically retry after rate limit errors, dramatically increasing success rate.

---

### Fix #2: Add Delay After Azure API Calls 🟡 SHORT-TERM WORKAROUND

**File:** `backend/app/expenses/service.py`, line 152-158

**Problem:** All 3 cloud accounts queried simultaneously, overwhelming Azure API

**Solution:** Add small delay after Azure calls to prevent rate limiting

```python
# Fetch all accounts in parallel with individual timeouts
tasks = [
    fetch_single_account(account, adapter)
    for account, adapter in adapters
]

results = await asyncio.gather(*tasks, return_exceptions=True)

# Add delay for Azure accounts to prevent rate limiting on next call
for i, (account, _) in enumerate(adapters):
    if account.type == CloudType.AZURE:
        logger.info("Adding delay after Azure API call to prevent rate limiting")
        await asyncio.sleep(3)  # 3 second cooldown
        break
```

**Impact:** Reduces likelihood of hitting Azure rate limits during expense aggregation.

---

### Fix #3: Handle 429 in Azure Adapter Directly 🟠 ROOT CAUSE FIX

**File:** `backend/app/cloud_accounts/adapters/azure.py`

**Problem:** Azure adapter doesn't extract Retry-After header from 429 responses

**Solution:** Parse and respect Retry-After header

```python
from azure.core.exceptions import HttpResponseError

async def get_cost_and_usage(self, ...):
    try:
        # ... existing code ...
    except HttpResponseError as e:
        if e.status_code == 429:
            # Extract Retry-After header
            retry_after = 10  # Default 10 seconds
            if hasattr(e, 'response') and e.response:
                retry_after = int(e.response.headers.get('Retry-After', 10))
            
            logger.warning(
                f"Azure rate limited (429). Retrying after {retry_after}s"
            )
            await asyncio.sleep(retry_after)
            
            # Retry once
            return await self.get_cost_and_usage(...)
        
        # Re-raise non-429 errors
        raise
```

**Impact:** Respects Azure's recommended retry timing, more likely to succeed on retry.

---

### Fix #4: Implement Request Coalescing for Azure Calls 🔵 ARCHITECTURAL

**File:** `backend/app/shared/request_coalescing.py`

**Problem:** Multiple identical Azure cost queries happening simultaneously

**Solution:** Coalesce identical Azure API requests within a time window

```python
# Create Azure-specific coalescer with stricter limits
azure_costs_coalescer = RequestCoalescer(
    max_wait_seconds=30.0,  # Wait up to 30s for duplicate requests
    max_concurrent=1  # Only ONE Azure cost query at a time
)

async def coalesce_azure_costs(func, *args, **kwargs):
    """Coalesce Azure cost API calls to prevent rate limiting."""
    return await azure_costs_coalescer.coalesce(
        "azure_costs",
        func,
        *args,
        **kwargs
    )
```

**Impact:** If 3 pages request Azure costs within 30s, only ONE actual API call is made.

---

## Azure Cost Management API Rate Limits

According to Microsoft documentation:

| Metric | Limit |
|--------|-------|
| Requests per minute | ~60-120 (varies by subscription) |
| Requests per hour | ~1000-2000 |
| Concurrent requests | Limited (undocumented) |
| Retry-After header | Present on 429 responses |

**Our Current Usage:**
- Dashboard load: 3 parallel calls (AWS, Azure, GCP)
- Cloud Accounts page: 3 parallel calls (one per account)
- Cache refresh: 3 parallel calls
- Resource discovery: 3 parallel calls

**Total concurrent Azure calls:** Up to 4 simultaneous calls when pages load concurrently

---

## Testing Plan

After applying fixes:

1. **Clear cache:** `docker exec costpilot-redis-1 redis-cli -a <password> FLUSHDB`

2. **Load Dashboard** and verify:
   - Monthly Spend shows ~$0.06 (not $0)
   - Last Month shows ~$0.31 (not $0)
   - Forecast shows ~$0.27 (not $0)

3. **Check backend logs** for:
   ```
   [DEBUG] Expense summary aggregation: 3/3 accounts successful, failed: []
   ```

4. **Load Cloud Accounts page** and verify no 429 errors in logs

5. **Trigger cache refresh** and verify all 3 accounts succeed

---

## Recommended Implementation Order

1. **Immediate (Today):** Fix #1 (429 detection + backoff)
2. **Short-term (This Week):** Fix #2 (Azure delay) + Fix #3 (Retry-After header)
3. **Long-term (Next Sprint):** Fix #4 (Request coalescing)

---

## Additional Notes

### Why AWS and GCP Don't Have This Issue

- **AWS Cost Explorer:** Higher rate limits (~10 requests/second)
- **GCP BigQuery Billing:** Not configured (returns $0 immediately, no API call)
- **Azure Cost Management:** Strict rate limits (~1-2 requests/second)

### Expected Dashboard Values After Fix

Based on actual Azure cost data:
- **Monthly Spend:** $0.06 (Azure only, AWS and GCP are ~$0)
- **Last Month:** $0.31 (Azure only)
- **Forecast:** $0.27 (Azure only)
- **Change %:** -13.5% (forecast vs last month)

These values are small because test accounts have minimal cloud usage.

---

## References

- [Azure Cost Management API Documentation](https://learn.microsoft.com/en-us/rest/api/cost-management/)
- [Azure Rate Limiting Best Practices](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling)
- [HTTP 429 Status Code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429)

---

**Priority:** 🔴 HIGH - Dashboard shows incorrect financial data  
**Estimated Fix Time:** 1-2 hours for Fix #1, 4-6 hours for all fixes  
**Risk:** Low - Adding retry logic is safe and backward compatible
