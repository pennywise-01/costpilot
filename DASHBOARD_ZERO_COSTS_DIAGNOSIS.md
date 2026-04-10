# Dashboard $0/mo Root Cause Analysis

**Date:** April 7, 2026  
**Issue:** Dashboard shows $0/mo for Monthly Spend, Forecast, and Last Month cards  
**Severity:** 🔴 HIGH - Financial data not displaying correctly  

---

## Problem Statement

The Dashboard page displays **$0/mo** for all three stat cards:
- Monthly Spend: $0
- Forecast: $0
- Last Month: $0

However, the Cloud Accounts (Data Sources) page shows actual cost data:
- AWS: $0/month
- **Azure: $0.06/month** ✅
- GCP: $0/month

This proves cost data EXISTS but is not being aggregated correctly for the Dashboard.

---

## Data Flow Analysis

### Dashboard Page Flow:
```
Dashboard.tsx
  ↓
expensesApi.getSummary(orgId)
  ↓
GET /api/v1/organizations/{org_id}/expenses/summary
  ↓
expense_summary() router function
  ↓
get_expenses_with_fallback(db, org_id)
  ↓
get_expense_summary(mongo_db, org_id)
  ↓
_fetch_cost_summary_with_coalescing(adapters)
  ↓
adapter.get_monthly_cost_summary() for each account
```

### Cloud Accounts Page Flow:
```
CloudAccounts.tsx
  ↓
cloudAccountsApi.getLiveData(accountId)
  ↓
GET /api/v1/cloud-accounts/{id}/live-data
  ↓
get_cloud_account_summary()
  ↓
adapter.get_monthly_cost_summary() for single account
```

---

## Evidence Collected

### 1. Browser Console Output
```javascript
[DEBUG] Fetching expense summary for orgId: 0ce62f26-8166-44ec-bf05-9c9025fdcb9c
[DEBUG] Expense summary response: {
  this_month_total: 0,
  last_month_total: 0,
  this_month_forecast: 0,
  change_percent: 0,
  data_source: "live"  // ← Not from cache!
}
```

### 2. Backend Logs - Cloud Accounts API (WORKING)
```
Azure: {'this_month': 0.06, 'last_month': 0.31, 'forecast': 0.27} ✅
AWS: {'this_month': -0.0, 'last_month': 0.0, 'forecast': -0.0}
GCP: {'this_month': 0.0, 'last_month': 0.0, 'forecast': 0.0}
```

### 3. Backend Logs - Expenses API (NOT WORKING)
```
[DEBUG] Found 3 cloud accounts for org 0ce62f26-...
[DEBUG] Account: testing, type: CloudType.AWS
[DEBUG] Account: testing, type: CloudType.AZURE  ← Should be here
[DEBUG] Account: testing-prod, type: CloudType.GCP

[DEBUG] Fetching cost summary from 3 adapters
[DEBUG] Calling get_monthly_cost_summary for account: testing (type: AWS)
[DEBUG] Cost summary for testing: this_month=-0.0, last_month=0.0, forecast=-0.0
[DEBUG] Cost summary for testing-prod: this_month=-0.0, last_month=0.0, forecast=-0.0
// ← Azure account is MISSING from the logs!
```

---

## Root Cause

**Azure Cost Management API is RATE-LIMITING our requests (HTTP 429 - Too Many Requests).**

### Evidence from Backend Logs:

```
azure.core.exceptions.HttpResponseError: (429) Too many requests. Please retry.
Code: 429
Message: Too many requests. Please retry.

Failed to fetch costs for account 733bf6e0-9c53-4c7b-b05a-468ad0c5742d: 
400: Cloud provider API error. Check server logs for details.

Cost cache refresh complete for org 0ce62f26-...: 2/3 accounts successful, total=$0.00
```

### What's Happening:

1. **Azure account HAS cost data**: $0.06 this month, $0.31 last month
2. **Multiple concurrent API calls** are being made to Azure Cost Management:
   - Cloud Accounts page calls `get_cloud_account_summary()` → Azure API
   - Dashboard calls `get_expense_summary()` → Azure API (again)
   - Cost cache refresh calls Azure API (again)
   - Resource discovery calls Azure Cost Management (again)

3. **Azure Cost Management API has strict rate limits** and is rejecting requests with HTTP 429
4. **The 429 error gets wrapped** in a BadRequestError (400) by our error handling
5. **Expense aggregation silently fails** for the Azure account and returns $0 total

### Why Cloud Accounts Page Shows $0.06 But Dashboard Shows $0:

- **Cloud Accounts page**: Calls each account individually with better timing
- **Dashboard expense API**: Calls all 3 accounts in parallel, hitting Azure's rate limit
- **Race condition**: Sometimes Azure API accepts the call, sometimes it rejects with 429

---

## Proposed Fixes

### Fix #1: Improve Error Logging (Immediate)

**File:** `backend/app/expenses/service.py`, line 140-150

**Current Code:**
```python
except Exception as e:
    logger.error(f"Error fetching costs for account {account.name}: {e}", exc_info=True)
    return None
```

**Proposed Fix:**
```python
except Exception as e:
    logger.error(
        f"Error fetching costs for account {account.name} "
        f"(id: {account.id}, type: {account.type}): {e}",
        exc_info=True,
        extra={
            "account_id": account.id,
            "account_type": account.type,
            "error_type": type(e).__name__,
        }
    )
    return None
```

This will help identify exactly which account is failing and why.

### Fix #2: Add Partial Failure Tracking (Short-term)

**File:** `backend/app/expenses/service.py`, line 153-163

**Current Code:**
```python
for result in results:
    if isinstance(result, dict):
        this_month_total += result.get("this_month", 0)
        last_month_total += result.get("last_month", 0)
        forecast_total += result.get("forecast", 0)
    elif isinstance(result, Exception):
        logger.error(f"Unexpected error fetching cost summary: {result}")
```

**Proposed Fix:**
```python
successful_accounts = 0
failed_accounts = []

for i, result in enumerate(results):
    if isinstance(result, dict):
        this_month_total += result.get("this_month", 0)
        last_month_total += result.get("last_month", 0)
        forecast_total += result.get("forecast", 0)
        successful_accounts += 1
    elif isinstance(result, Exception):
        failed_account = adapters[i][0] if i < len(adapters) else "unknown"
        failed_accounts.append(failed_account.name)
        logger.error(f"Failed to fetch costs for account: {failed_account.name}")

logger.info(
    f"Expense summary: {successful_accounts}/{len(adapters)} accounts successful, "
    f"failed: {failed_accounts}"
)
```

### Fix #3: Check Azure Adapter Initialization (Root Cause Fix)

**Investigate:** Why is the Azure account failing in the expense service but working in the cloud accounts service?

**Steps:**
1. Add debug logging to Azure adapter initialization in `_get_cloud_adapters()`
2. Check if the Azure config is being decrypted correctly
3. Verify Azure credentials are valid
4. Test Azure Cost Management API call directly

**File to check:** `backend/app/cloud_accounts/adapters/azure.py`

### Fix #4: Deduplicate Account Names (Data Quality)

**Issue:** Both AWS and Azure accounts are named "testing" which makes debugging difficult.

**Fix:** Update account names to be unique:
- AWS: "testing-aws"
- Azure: "testing-azure"
- GCP: "testing-prod" (already unique)

---

## Testing Plan

After applying fixes:

1. **Check backend logs** for detailed error messages showing which account fails
2. **Verify Azure account** is included in expense aggregation
3. **Confirm Dashboard displays** non-zero values:
   - Monthly Spend: Should show ~$0.06 (Azure)
   - Last Month: Should show ~$0.31 (Azure)
   - Forecast: Should show ~$0.27 (Azure)
4. **Test with all three cloud providers** to ensure none are silently failing

---

## Additional Notes

### AWS Costs Are Essentially Zero
```
this_month_cost=-4.62e-08 (negative 0.0000000462)
last_month_cost=1.24e-08 (positive 0.0000000124)
```
These are rounding artifacts from AWS Cost Explorer API. The actual costs are so small they're negligible.

### GCP Costs Are Zero Due to Missing Billing Export
GCP requires BigQuery billing export to be configured. Without it, the adapter falls back to estimated costs which return $0.

### Expected Dashboard Values After Fix
Based on cloud accounts data:
- **Monthly Spend:** $0.06 (Azure only, AWS and GCP are ~$0)
- **Last Month:** $0.31 (Azure only)
- **Forecast:** $0.27 (Azure only)

These values are small because the test accounts have minimal cloud usage.

---

## Priority

🔴 **HIGH** - Users cannot see their actual cloud spending on the dashboard, which is the primary value proposition of the CostPilot platform.

**Recommended Action:** Apply Fix #1 and #2 immediately to get visibility into the issue, then investigate Fix #3 to resolve the root cause.
