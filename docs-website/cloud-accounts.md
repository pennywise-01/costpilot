# Cloud Accounts Management

![Cloud Accounts List](screenshots/cloud-accounts-list.png)

Connect, manage, and monitor your AWS, Azure, GCP, and other cloud provider accounts in CostPilot.

---

## Overview

Cloud Accounts (also called "Data Sources") are the foundation of CostPilot's cost tracking capabilities. Each connected cloud account provides access to cost data, resource inventory, and optimization recommendations from that provider.

**URL**: `/cloud-accounts`

**Key Features:**
- Multi-cloud support (AWS, Azure, GCP, Alibaba Cloud, Kubernetes, Nebius)
- Encrypted credential storage
- Live cost data with intelligent caching
- Resource discovery
- Credential validation before account creation
- Graceful degradation with stale-cache fallback

---

## Connecting a Cloud Account

![Connect Cloud Account](screenshots/connect-cloud-account.png)

**As shown in the screenshot above:**
- Navigate to **Cloud Accounts** from the left sidebar
- You'll see an empty state with "Connect Your First Account" call-to-action
- Click the button to go to the provider selection page
- Choose from available providers:
  - **AWS** (Amazon Web Services)
  - **Azure** (Microsoft Azure)
  - **GCP** (Google Cloud Platform)
  - **Alibaba Cloud**
  - **Kubernetes**
  - **Nebius**

### Step-by-Step Guide

1. **Navigate to Cloud Accounts**
   - Click **"Cloud Accounts"** in the left sidebar
   - Click **"Connect Cloud Account"** button

2. **Select Cloud Provider**
   - Choose from AWS, Azure, or GCP
   - The form will update to show provider-specific fields

3. **Enter Credentials**
   - Fill in the required fields (see provider-specific details below)
   - Account name will be auto-generated or you can customize it

4. **Validate & Connect**
   - Click **"Validate & Connect"**
   - CostPilot will test the credentials by making a test API call
   - If validation succeeds, the account will be created
   - If validation fails, you'll see an error message with details

5. **Initial Data Collection**
   - After account creation, the scheduler will begin collecting data
   - This may take a few minutes for the first run
   - You can view progress on the account details page

---

## Provider-Specific Configuration

### Amazon Web Services (AWS)

**Required Credentials:**
- **Access Key ID**: AWS IAM access key ID
- **Secret Access Key**: AWS IAM secret access key
- **Region** (Optional): Default region for API calls (defaults to `us-east-1`)

**Required IAM Permissions:**

Create an IAM policy with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeRegions"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets"
      ],
      "Resource": "*"
    }
  ]
}
```

**Best Practices:**
- Create a dedicated IAM user for CostPilot
- Use read-only permissions only
- Rotate access keys regularly
- Enable MFA on the IAM user

**Supported Services:**
- EC2 (Elastic Compute Cloud)
- RDS (Relational Database Service)
- Lambda (Serverless Functions)
- S3 (Simple Storage Service)
- And more via cost data

---

### Microsoft Azure

**Required Credentials:**
- **Subscription ID**: Azure subscription identifier (UUID)
- **Client ID**: Azure AD application (service principal) client ID
- **Client Secret**: Azure AD application client secret
- **Tenant ID**: Azure AD tenant ID

**Required Permissions:**

Assign these roles to your service principal:

1. **Cost Management Reader**
   - Allows reading cost data and forecasts
   - Scope: Subscription level

2. **Reader**
   - Allows reading resource metadata
   - Scope: Subscription level

**Setup Steps:**

1. **Register an Azure AD Application:**
   ```bash
   az ad app create --display-name "CostPilot"
   ```

2. **Create a Service Principal:**
   ```bash
   az ad sp create --id <application-id>
   ```

3. **Create a Client Secret:**
   - Navigate to Azure Portal > Azure Active Directory > App Registrations
   - Select your application
   - Go to **Certificates & secrets**
   - Create a new client secret (valid for 24 months recommended)

4. **Assign Roles:**
   ```bash
   az role assignment create \
     --assignee <service-principal-id> \
     --role "Cost Management Reader" \
     --scope /subscriptions/<subscription-id>
   
   az role assignment create \
     --assignee <service-principal-id> \
     --role "Reader" \
     --scope /subscriptions/<subscription-id>
   ```

**Supported Services:**
- Virtual Machines
- App Services
- Azure SQL Database
- Blob Storage
- And more via cost data

---

### Google Cloud Platform (GCP)

**Required Credentials:**
- **Credentials JSON**: Service account key file (JSON format)
- **Organization ID** or **Project ID**: GCP organization or billing project ID

**Required IAM Roles:**

1. **Billing Account Viewer** (`roles/billing.viewer`)
   - Allows reading billing and cost data
   - Grant at the billing account level

2. **Compute Viewer** (`roles/compute.viewer`)
   - Allows reading resource metadata
   - Grant at the project or organization level

**Setup Steps:**

1. **Create a Service Account:**
   ```bash
   gcloud iam service-accounts create costpilot \
     --display-name="CostPilot Service Account"
   ```

2. **Grant Roles:**
   ```bash
   # Billing Viewer role
   gcloud billing accounts add-iam-policy-binding <billing-account-id> \
     --member="serviceAccount:costpilot@<project-id>.iam.gserviceaccount.com" \
     --role="roles/billing.viewer"
   
   # Compute Viewer role
   gcloud projects add-iam-policy-binding <project-id> \
     --member="serviceAccount:costpilot@<project-id>.iam.gserviceaccount.com" \
     --role="roles/compute.viewer"
   ```

3. **Create and Download Key:**
   ```bash
   gcloud iam service-accounts keys create costpilot-key.json \
     --iam-account=costpilot@<project-id>.iam.gserviceaccount.com
   ```

4. **Upload the JSON file** to CostPilot when connecting the account

**Supported Services:**
- Compute Engine
- Cloud SQL
- Cloud Functions
- Cloud Storage
- And more via cost data

---

## Managing Cloud Accounts

### Viewing Accounts

![Cloud Accounts List](screenshots/cloud-accounts-list.png)

The Cloud Accounts list page shows:

- **Account Name**: Provider and identifier
- **Cloud Provider**: AWS, Azure, or GCP icon
- **Status**: Active, Error, or Collecting Data
- **This Month's Cost**: Current month spend
- **Trend**: Change vs. last month (percentage)
- **Last Updated**: When data was last collected

### Account Details Page

Click on an account to view details:

**Information Displayed:**
- Account metadata (provider, region, organization)
- Live cost data (with 5-minute cache)
- Resource inventory summary
- Cost history sparkline (30 days)
- Recent recommendations for this account

**Actions:**
- **Refresh**: Force fetch of live data from cloud provider
- **Edit**: Update account credentials or settings
- **Delete**: Remove the account (soft delete)

### Editing an Account

1. Navigate to account details
2. Click **"Edit"**
3. Update credentials or settings
4. Click **"Save"**
5. Credentials will be re-validated

### Deleting an Account

1. Navigate to account details
2. Click **"Delete"**
3. Confirm the deletion
4. The account is soft-deleted (data retained for reporting)

**Note:** Deleting an account stops data collection but preserves historical data for reporting purposes.

---

## Live Data & Caching

### Cache Strategy

CostPilot uses an intelligent caching strategy to balance performance and freshness:

| Data Type | TTL | Fallback |
|-----------|-----|----------|
| Live Cost Data | 5 minutes | Stale cache (up to 24 hours) |
| Resource Inventory | 5 minutes | Stale cache |
| Cost History | 5 minutes | Stale cache |
| Recommendations | 10 minutes | Re-run recommendation engine |

### Force Refresh

To bypass cache and fetch live data:

1. Navigate to account details page
2. Click **"Refresh"** button
3. Set `force_refresh=true` in API call
4. Wait for response (may take 10-30 seconds)

### Graceful Degradation

If cloud provider APIs are unavailable:
- CostPilot returns stale cached data
- A "stale" indicator is shown in the UI
- No errors are displayed to the user
- Scheduler retries automatically

---

## API Endpoints

### List Cloud Accounts
```
GET /api/v1/organizations/{org_id}/cloud-accounts
```

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 50)

**Response:**
```json
{
  "accounts": [
    {
      "id": "uuid",
      "name": "Production AWS",
      "cloud_type": "aws",
      "region": "us-east-1",
      "status": "active",
      "monthly_cost": 1234.56,
      "trend_pct": 5.2,
      "last_updated": "2026-04-09T12:00:00Z"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 50
}
```

### Create Cloud Account
```
POST /api/v1/organizations/{org_id}/cloud-accounts
```

**Request Body:**
```json
{
  "cloud_type": "aws",
  "name": "My AWS Account",
  "credentials": {
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "region": "us-east-1"
  }
}
```

### Get Account Live Data
```
GET /api/v1/cloud-accounts/{id}/live-data?force_refresh=false
```

**Response:**
```json
{
  "account_id": "uuid",
  "total_cost": 1234.56,
  "currency": "USD",
  "resource_count": 150,
  "cost_by_service": [
    {"service": "EC2", "cost": 800.00},
    {"service": "RDS", "cost": 300.00}
  ],
  "cost_history": [
    {"date": "2026-04-01", "cost": 40.00},
    {"date": "2026-04-02", "cost": 42.50}
  ]
}
```

### Get Account Resources
```
GET /api/v1/cloud-accounts/{id}/resources?limit=50
```

### Get Cost History
```
GET /api/v1/cloud-accounts/{id}/cost-history?days=30
```

### Update Account
```
PATCH /api/v1/cloud-accounts/{id}
```

### Delete Account
```
DELETE /api/v1/cloud-accounts/{id}
```

---

## Security

### Credential Encryption

- All cloud credentials are encrypted using **Fernet symmetric encryption**
- Encryption key is stored in `ENCRYPTION_KEY` environment variable
- Credentials are encrypted before storage in PostgreSQL
- Decryption only occurs when making API calls to cloud providers

### Best Practices

1. **Rotate Credentials Regularly**
   - AWS: Rotate IAM keys every 90 days
   - Azure: Renew client secrets before expiry
   - GCP: Rotate service account keys

2. **Use Minimum Required Permissions**
   - Follow least-privilege principle
   - Only grant read-only access
   - Avoid using admin/root credentials

3. **Monitor API Usage**
   - Watch for rate limiting errors
   - Monitor cloud provider API costs
   - Set up billing alerts in cloud consoles

4. **Secure Your CostPilot Instance**
   - Use strong JWT secrets
   - Enable HTTPS in production
   - Restrict access to CostPilot UI/API

---

## Troubleshooting

### Credential Validation Fails

**AWS:**
- Check that access key ID and secret are correct
- Verify IAM permissions are attached
- Ensure the key is not expired or revoked
- Check for typos in the region

**Azure:**
- Verify subscription ID exists and is active
- Check that service principal exists
- Ensure client secret is not expired
- Verify role assignments are correct
- Check tenant ID matches your Azure AD

**GCP:**
- Validate JSON format is correct
- Ensure service account exists
- Verify roles are granted at correct scope
- Check billing is enabled for the project

### No Cost Data Appears

**Possible Causes:**
1. Account recently connected (data collection in progress)
2. Scheduler not running
3. Cloud provider API errors
4. No actual costs incurred

**Solutions:**
1. Wait a few minutes for initial collection
2. Check **Schedulers** page for expense collection status
3. Try manual refresh on account details page
4. Verify costs exist in cloud provider console

### Rate Limiting Errors

**Azure Rate Limiting:**
- Azure Cost Management API has strict rate limits
- CostPilot implements automatic retry with exponential backoff
- If you see rate limiting, reduce scheduler frequency

**Solutions:**
- Increase scheduler interval (e.g., from 60 to 120 minutes)
- Stagger scheduler times for multiple accounts
- Contact cloud provider to increase rate limits

---

## Next Steps

- **[Dashboard](dashboard.md)** - View costs on the main dashboard
- **[Expense Tracking](expenses.md)** - Deep dive into cost analysis
- **[Resource Discovery](resources.md)** - Explore discovered resources
- **[Schedulers](schedulers.md)** - Configure automated data collection

---

**Related Documentation:**
- [How to Add Cloud Accounts](guides/add-cloud-account.md)
- [API Reference](api-reference.md)
- [Security Best Practices](security-best-practices.md)
