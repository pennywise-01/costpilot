# Cloud Provider Issues - Documentation

This document details all cloud provider (GCP, Azure, AWS) related issues discovered during comprehensive testing. These issues require cloud provider configuration changes and are not application code bugs.

---

## Table of Contents
- [GCP Issues](#gcp-issues)
- [Azure Issues](#azure-issues)
- [AWS Issues](#aws-issues)
- [Resolution Checklist](#resolution-checklist)

---

## GCP Issues

### Issue 1: GCP Recommendations Fetch Failure 🔴 CRITICAL

**Error Message:**
```
ERROR: Failed to fetch GCP recommendations
DefaultCredentialsError: Your default credentials were not found
```

**Backend Log:**
```json
{
  "timestamp": "2026-04-07 12:21:59,154",
  "level": "ERROR",
  "logger": "app.recommendations.adapters.gcp",
  "message": "Failed to fetch GCP recommendations",
  "exception": {
    "type": "DefaultCredentialsError",
    "message": "google.auth.exceptions.DefaultCredentialsError: Your default credentials were not found. To set up Application Default Credentials, see https://cloud.google.com/docs/authentication/external/set-up-adc for more information."
  }
}
```

**File:** `backend/app/recommendations/adapters/gcp.py`, line 32

**Root Cause:**
The GCP RecommenderClient is trying to use Application Default Credentials (ADC) which are not configured in the Docker container. The code at line 32 creates the client without passing credentials:

```python
client = recommender_v1.RecommenderClient()  # Tries to use ADC
```

**Impact:**
- GCP recommendations never appear in the Recommendations page
- Users see zero potential savings from GCP resources
- Recommendation overview shows incomplete data

**Resolution Options:**

**Option A: Configure Application Default Credentials (Recommended for Production)**
1. Create a GCP Service Account with the following roles:
   - `Recommender Viewer`
   - `Billing Viewer`
2. Download the service account key JSON file
3. Mount the credentials into the Docker container:
   ```yaml
   # docker-compose.yml
   services:
     backend:
       environment:
         - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/gcp-key.json
       volumes:
         - ./gcp-credentials:/app/credentials:ro
   ```

**Option B: Pass Credentials Explicitly**
```python
# In backend/app/recommendations/adapters/gcp.py
from google.oauth2 import service_account

def _fetch_sync(self, config):
    credentials = service_account.Credentials.from_service_account_file(
        config.get('credentials_path', '/app/credentials/gcp-key.json')
    )
    client = recommender_v1.RecommenderClient(credentials=credentials)
    # ... rest of the code
```

**Required GCP API Permissions:**
- `recommender.googleapis.com` must be enabled
- `billing.googleapis.com` must be enabled
- `cloudresourcemanager.googleapis.com` must be enabled

---

### Issue 2: Missing `google-cloud-functions` Package 🟡 MEDIUM

**Error Message:**
```
WARNING: Failed to scan project ai-search-production-477802: cannot import name 'functions_v2' from 'google.cloud'
```

**Backend Log:**
```json
{
  "timestamp": "2026-04-07 12:21:19,050",
  "level": "WARNING",
  "logger": "app.cloud_accounts.adapters.gcp",
  "message": "Failed to scan project ai-search-production-477802: cannot import name 'functions_v2' from 'google.cloud' (unknown location)"
}
```

**File:** `backend/app/cloud_accounts/adapters/gcp.py`, line 892

**Root Cause:**
The code imports `google.cloud.functions_v2` but the `google-cloud-functions` package is not listed in `pyproject.toml` dependencies.

**Impact:**
- Cloud Functions v2 resources are not discovered during resource scanning
- Users cannot see their GCP Cloud Functions in the Resources page
- Resource count is lower than actual

**Resolution:**

Add the missing dependency to `backend/pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies
    "google-cloud-functions>=1.15.0",
]
```

Then rebuild the Docker image:
```bash
docker compose build backend
docker compose up -d backend
```

**Required GCP API Permissions:**
- `cloudfunctions.googleapis.com` must be enabled
- Service Account needs `Cloud Functions Viewer` role

---

### Issue 3: GCP BigQuery Billing Export Not Configured 🟡 MEDIUM

**Error Message:**
```
WARNING: BigQuery billing export not available: 404 No billing export table found
WARNING: Using estimated costs - BigQuery billing export not configured
```

**Backend Log:**
```json
{
  "timestamp": "2026-04-07 12:21:03,091",
  "level": "WARNING",
  "logger": "app.cloud_accounts.adapters.gcp",
  "message": "BigQuery billing export not available: 404 No billing export table found"
}
```

**File:** `backend/app/cloud_accounts/adapters/gcp.py`, line 394

**Root Cause:**
The GCP project `ai-search-production-477802` does not have BigQuery billing export configured. The adapter tries to query billing data from BigQuery but the table doesn't exist, so it falls back to estimated costs which return $0.

**Impact:**
- All GCP costs show as $0.00
- Monthly spend calculations are incorrect
- Cost trends show no data
- Forecast calculations are inaccurate

**Resolution Steps:**

1. **Enable BigQuery API** (if not already enabled):
   ```bash
   gcloud services enable bigquery.googleapis.com --project=ai-search-production-477802
   ```

2. **Create BigQuery Dataset:**
   - Go to GCP Console → BigQuery
   - Create a dataset (e.g., `billing_export`)
   - Choose US or EU location

3. **Configure Billing Export:**
   - Go to GCP Console → Billing → Billing export
   - Click "Edit settings" for Standard Google Cloud Billing
   - Select "Export to BigQuery"
   - Choose the dataset created in step 2
   - Save

4. **Wait for Data Population:**
   - Billing export can take 24-48 hours to start showing data
   - Initial backfill may take up to 72 hours

5. **Update Backend Configuration (if needed):**
   ```python
   # In cloud account config, specify the billing table
   billing_table_id = "ai-search-production-477802.billing_export.gcp_billing_export_v1_xxxx"
   ```

**Reference:** [GCP Billing Export Documentation](https://cloud.google.com/billing/docs/how-to/export-data-bigquery)

---

## Azure Issues

### Issue 4: Azure Cost Management API 400 Error 🟡 MEDIUM

**Error Message:**
```
WARNING: Azure Cost Management API error: Cloud provider API error. Check server logs for details.
ERROR: Function failed after 1 attempts
WARNING: Failed to enrich resources with costs: 400: Cloud provider API error. Check server logs for details.
```

**Backend Log:**
```json
{
  "timestamp": "2026-04-07 12:13:28,434",
  "level": "ERROR",
  "logger": "app.shared.retry",
  "message": "Function failed after 1 attempts",
  "extra": {
    "errors": ["400: Cloud provider API error. Check server logs for details."]
  }
}
```

**File:** `backend/app/cloud_accounts/adapters/azure.py`, line 233

**Root Cause:**
The Azure Cost Management API is returning a 400 error. This can be caused by:

1. **Missing Permissions:** Service Principal lacks "Cost Management Reader" role
2. **Subscription Type:** Some subscription types (e.g., Free Trial, MSDN) don't support Cost Management API
3. **API Version:** Using deprecated API version
4. **Query Parameters:** Invalid date range or aggregation parameters

**Impact:**
- Azure resource costs cannot be fetched from Cost Management API
- Resources show $0 or estimated costs
- Cost breakdown by Azure services is missing
- Monthly Azure spend calculations are inaccurate

**Resolution Steps:**

1. **Verify Service Principal Permissions:**
   ```bash
   # Check if Service Principal has Cost Management Reader role
   az role assignment list --assignee <CLIENT_ID> --all
   
   # Assign Cost Management Reader role if missing
   az role assignment create \
     --assignee <CLIENT_ID> \
     --role "Cost Management Reader" \
     --scope /subscriptions/<SUBSCRIPTION_ID>
   ```

2. **Verify Subscription Supportss Cost Management:**
   ```bash
   # Check subscription type
   az account show --subscription <SUBSCRIPTION_ID>
   
   # Cost Management is NOT available for:
   # - Free Trial subscriptions
   # - Azure Pass subscriptions
   # - Some MSDN/Visual Studio subscriptions
   ```

3. **Test Cost Management API Access:**
   ```bash
   # Get access token
   TOKEN=$(az account get-access-token --resource https://management.azure.com/ --query accessToken -o tsv)
   
   # Test API call
   curl -X POST \
     "https://management.azure.com/subscriptions/<SUBSCRIPTION_ID>/providers/Microsoft.CostManagement/query?api-version=2023-03-01" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "type": "ActualCost",
       "timeframe": "MonthToDate",
       "dataset": {
         "granularity": "Daily",
         "aggregation": {
           "totalCost": {
             "name": "Cost",
             "function": "Sum"
           }
         }
       }
     }'
   ```

4. **Add Better Error Handling (Code Improvement):**
   ```python
   # In backend/app/cloud_accounts/adapters/azure.py
   except HttpResponseError as e:
       if e.status_code == 400:
           logger.error(
               f"Azure Cost Management 400 error for subscription {self.subscription_id}: "
               f"{e.message}. This may indicate insufficient permissions or "
               f"unsupported subscription type."
           )
           raise BadRequestError(
               "Azure Cost Management API returned 400. "
               "Please verify the Service Principal has 'Cost Management Reader' role "
               "and that the subscription supportss Cost Management API."
           )
   ```

**Reference:** [Azure Cost Management API Documentation](https://learn.microsoft.com/en-us/rest/api/cost-management/)

---

## AWS Issues

### Issue 5: No AWS Errors Detected ✅

**Status:** All AWS adapters are functioning correctly during testing.

**Verified Working:**
- ✅ AWS resource discovery (EC2, S3)
- ✅ AWS cost data retrieval
- ✅ AWS recommendations fetching

**Note:** While no errors were found during testing, ensure the following for production readiness:

1. **AWS Credentials Rotation:**
   - Access keys should be rotated every 90 days
   - Use IAM roles instead of access keys when possible

2. **Cost Explorer API Permissions:**
   - IAM user/role needs `ce:GetCostAndUsage` permission
   - Enable Cost Explorer in AWS Billing Console

3. **AWS Recommendations:**
   - Requires `ec2:DescribeInstances` for Compute Optimizer
   - Enable Compute Optimizer in AWS Console

---

## Resolution Checklist

### Immediate Actions (This Week)

- [ ] **GCP Recommendations:** Configure Application Default Credentials
  - [ ] Create GCP Service Account
  - [ ] Download JSON key
  - [ ] Mount into Docker container
  - [ ] Test recommendations fetch

- [ ] **GCP Cloud Functions:** Add missing dependency
  - [ ] Add `google-cloud-functions>=1.15.0` to `pyproject.toml`
  - [ ] Rebuild Docker image
  - [ ] Verify Cloud Functions appear in Resources

### High Priority (Next Sprint)

- [ ] **GCP Billing Export:** Configure BigQuery billing export
  - [ ] Enable BigQuery API
  - [ ] Create dataset
  - [ ] Configure billing export in GCP Console
  - [ ] Wait 24-48 hours for data population
  - [ ] Verify costs appear correctly

- [ ] **Azure Cost Management:** Fix API access
  - [ ] Check Service Principal permissions
  - [ ] Assign "Cost Management Reader" role
  - [ ] Verify subscription type supports Cost Management
  - [ ] Test API access with curl
  - [ ] Verify Azure costs appear

### Medium Priority

- [ ] **GCP API Enablement:** Ensure all required APIs are enabled
  - [ ] `recommender.googleapis.com`
  - [ ] `cloudfunctions.googleapis.com`
  - [ ] `bigquery.googleapis.com`

- [ ] **Azure Permissions Audit:** Review all Azure Service Principal roles
  - [ ] Cost Management Reader
  - [ ] Reader (for resource discovery)
  - [ ] Storage Blob Data Reader (if using storage accounts)

- [ ] **AWS Best Practices:** Long-term maintenance
  - [ ] Set up credential rotation schedule
  - [ ] Review IAM policies quarterly
  - [ ] Enable AWS Compute Optimizer

---

## Testing Verification

After resolving each issue, verify with these steps:

1. **GCP Recommendations:**
   ```bash
   # Check backend logs
   docker logs costpilot-backend-1 | grep -i "recommendation"
   
   # Should see: "Fetched X recommendations from GCP"
   ```

2. **GCP Cloud Functions:**
   - Navigate to Resources page
   - Filter by Cloud Type: GCP
   - Verify Cloud Functions appear in list

3. **GCP Billing:**
   - Navigate to Dashboard
   - Verify GCP monthly cost shows non-zero value
   - Check Cost Explorer for GCP cost breakdown

4. **Azure Cost Management:**
   - Navigate to Resources page
   - Click on an Azure resource
   - Verify cost data appears in detail view
   - Check Dashboard for Azure monthly spend

---

## Support Contacts

If issues persist after following this documentation:

- **GCP Support:** https://cloud.google.com/support
- **Azure Support:** https://azure.microsoft.com/en-us/support/
- **AWS Support:** https://aws.amazon.com/contact-us/

---

**Last Updated:** April 7, 2026  
**Tested By:** Automated browser testing + backend log monitoring  
**Test Duration:** Full application walkthrough with all interactive elements tested
