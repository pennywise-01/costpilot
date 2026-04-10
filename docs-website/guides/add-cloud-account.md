# How to Add Cloud Accounts

Step-by-step guide to connecting your AWS, Azure, and GCP accounts to CostPilot.

---

## Overview

Connecting cloud accounts is the first step in using CostPilot. This guide walks you through connecting each supported cloud provider with proper credentials and permissions.

**Time Required:** 10-15 minutes per account  
**Prerequisites:** 
- Access to cloud provider console
- Permission to create IAM users/service principals
- CostPilot Organization Admin or Engineer role

---

## AWS Account Setup

### Step 1: Create IAM User

1. Log in to AWS Console
2. Navigate to **IAM** > **Users**
3. Click **"Create user"**
4. Enter user name: `costpilot-integration`
5. Select **"Attach policies directly"**
6. Proceed to create user (don't attach policies yet)
7. After creation, go to user details
8. Navigate to **Security credentials** tab
9. Click **"Create access key"**
10. Select **"Other"** as use case
11. Save the **Access Key ID** and **Secret Access Key**

---

### Step 2: Attach IAM Policy

1. In IAM user details, go to **Permissions** tab
2. Click **"Add permissions"** > **"Create inline policy"**
3. Switch to **JSON** tab
4. Paste this policy:

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

5. Click **"Next"**
6. Name policy: `CostPilotAccessPolicy`
7. Click **"Create policy"**

---

### Step 3: Connect to CostPilot

1. In CostPilot, navigate to **Cloud Accounts**
2. Click **"Connect Cloud Account"**
3. Select **AWS** as provider
4. Fill in:
   - **Account Name**: `Production AWS` (or your preferred name)
   - **Access Key ID**: From step 1
   - **Secret Access Key**: From step 1
   - **Region**: `us-east-1` (or your primary region, optional)
5. Click **"Validate & Connect"**
6. Wait for validation (10-30 seconds)
7. Success! Account is connected

---

### Step 4: Verify Connection

1. Click on the account to view details
2. You should see:
   - Account metadata
   - Live cost data (may take a few minutes to populate)
   - Resource count
3. Navigate to **Resources** page to see discovered AWS resources

---

## Azure Account Setup

### Step 1: Register Azure AD Application

1. Log in to Azure Portal
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **"New registration"**
4. Enter name: `CostPilot`
5. Select **"Accounts in this organizational directory only"**
6. Click **"Register"**
7. Save the **Application (client) ID** and **Directory (tenant) ID**

---

### Step 2: Create Client Secret

1. In app registration, go to **Certificates & secrets**
2. Click **"New client secret"**
3. Description: `CostPilot Secret`
4. Expires: **24 months** (recommended)
5. Click **"Add"**
6. **Immediately copy the secret value** (you won't see it again)

---

### Step 3: Assign Roles

1. Navigate to **Subscriptions**
2. Select your subscription
3. Go to **Access control (IAM)**
4. Click **"Add"** > **"Add role assignment"**

**First Role - Cost Management Reader:**
5. Search for **"Cost Management Reader"**
6. Select it and click **"Next"**
7. Click **"+ Select members"**
8. Search for your app registration (`CostPilot`)
9. Select it and click **"Select"**
10. Click **"Review + assign"**

**Second Role - Reader:**
11. Repeat steps 4-10
12. Select **"Reader"** role instead
13. Assign to same app registration

---

### Step 4: Get Subscription ID

1. Navigate to **Subscriptions**
2. Copy the **Subscription ID** (UUID format)

---

### Step 5: Connect to CostPilot

1. In CostPilot, navigate to **Cloud Accounts**
2. Click **"Connect Cloud Account"**
3. Select **Azure** as provider
4. Fill in:
   - **Account Name**: `Production Azure` (or your preferred name)
   - **Subscription ID**: From step 4
   - **Client ID**: From step 1
   - **Client Secret**: From step 2
   - **Tenant ID**: From step 1
5. Click **"Validate & Connect"**
6. Wait for validation (10-30 seconds)
7. Success! Account is connected

---

### Step 6: Verify Connection

1. View account details
2. Check cost data and resources appear
3. Navigate to **Resources** to see Azure resources

---

## GCP Account Setup

### Step 1: Create Service Account

1. Log in to Google Cloud Console
2. Navigate to **IAM & Admin** > **Service Accounts**
3. Click **"Create Service Account"**
4. Name: `costpilot`
5. Description: `CostPilot integration service account`
6. Click **"Create and Continue"**
7. Don't grant roles yet (we'll do this at billing/project level)
8. Click **"Done"**

---

### Step 2: Grant Billing Viewer Role

1. Navigate to **Billing**
2. Select your billing account
3. Go to **Permissions**
4. Click **"Add members"**
5. Enter service account email: `costpilot@<project-id>.iam.gserviceaccount.com`
6. Select role: **Billing** > **Billing Account Viewer**
7. Click **"Save"**

---

### Step 3: Grant Compute Viewer Role

1. Navigate to **IAM & Admin** > **IAM**
2. Click **"Add"**
3. Enter service account email
4. Select role: **Compute Engine** > **Compute Viewer**
5. Click **"Save"**

---

### Step 4: Create and Download Key

1. Go back to **Service Accounts**
2. Click on `costpilot` service account
3. Go to **Keys** tab
4. Click **"Add Key"** > **"Create new key"**
5. Key type: **JSON**
6. Click **"Create"**
7. JSON file downloads automatically
8. Keep this file secure!

---

### Step 5: Connect to CostPilot

1. In CostPilot, navigate to **Cloud Accounts**
2. Click **"Connect Cloud Account"**
3. Select **GCP** as provider
4. Fill in:
   - **Account Name**: `Production GCP` (or your preferred name)
   - **Credentials JSON**: Open the downloaded JSON file, copy entire contents, paste here
   - **Project ID**: Your GCP project ID (from JSON file or console)
5. Click **"Validate & Connect"**
6. Wait for validation (10-30 seconds)
7. Success! Account is connected

---

### Step 6: Verify Connection

1. View account details
2. Check cost data and resources appear
3. Navigate to **Resources** to see GCP resources

---

## Post-Connection Steps

### 1. Wait for Data Collection

After connecting accounts:
- Schedulers automatically start collecting data
- Initial collection takes 5-15 minutes
- Check **Schedulers** page for progress

### 2. Verify Costs Appear

1. Navigate to **Dashboard**
2. Wait for costs to appear (may take up to 30 minutes for first collection)
3. Check **Expenses** page for detailed breakdown

### 3. Check Resources

1. Navigate to **Resources** page
2. Verify resources from connected accounts appear
3. Check resource details for completeness

### 4. Review Recommendations

1. Navigate to **Recommendations** page
2. Wait for recommendation engine to analyze (may take up to 1 hour)
3. Review and act on recommendations

---

## Troubleshooting

### AWS: "Invalid credentials"

**Check:**
- Access Key ID and Secret Access Key are correct (no extra spaces)
- IAM user exists and is not disabled
- Policy is attached to the user
- Credentials are not expired or revoked

**Solution:**
- Re-create access key in AWS console
- Re-attach policy
- Try again in CostPilot

---

### Azure: "Subscription not found"

**Check:**
- Subscription ID is correct (copy from Azure Portal)
- Service principal has access to subscription
- Role assignments are correct

**Solution:**
- Verify Subscription ID in Azure Portal > Subscriptions
- Re-assign roles to service principal
- Ensure using correct Azure AD tenant

---

### Azure: "Permission denied"

**Check:**
- Cost Management Reader role is assigned
- Reader role is assigned
- Role assignment scope is correct (subscription level)

**Solution:**
- Re-assign both roles
- Wait 5-10 minutes for role propagation
- Try again

---

### GCP: "Invalid JSON format"

**Check:**
- JSON file is valid (not corrupted)
- Copied entire file contents
- No extra characters or line breaks

**Solution:**
- Re-download JSON file
- Copy contents carefully
- Use file upload if available

---

### GCP: "Billing not enabled"

**Check:**
- Billing account exists and is active
- Service account has Billing Account Viewer role
- Project has billing enabled

**Solution:**
- Enable billing on project
- Grant Billing Account Viewer role
- Wait a few minutes for propagation

---

### No Costs Appearing After Connection

**Possible Causes:**
1. No actual costs incurred yet
2. Scheduler hasn't run yet
3. Cloud provider API returning no data
4. Date range too narrow

**Solutions:**
1. Check cloud provider console for actual costs
2. Manually trigger scheduler on **Schedulers** page
3. Check backend logs for errors
4. Expand date range on **Expenses** page

---

## Best Practices

1. **Use Dedicated Credentials**: Don't use personal/admin credentials
2. **Rotate Keys Regularly**: Rotate access keys/secrets every 90 days
3. **Monitor API Usage**: Watch for rate limiting or unexpected API costs
4. **Document Credentials**: Store credentials securely (password manager, secrets manager)
5. **Test in Dev First**: If possible, test with non-production accounts first
6. **Name Accounts Clearly**: Use descriptive names for easy identification
7. **Verify Permissions**: Double-check permissions before connecting

---

## Next Steps

Now that your cloud accounts are connected:

- **[Dashboard](../dashboard.md)** - View your cost overview
- **[Expense Tracking](../expenses.md)** - Analyze costs in detail
- **[Resource Discovery](../resources.md)** - Explore discovered resources
- **[Schedulers](../schedulers.md)** - Configure automated data collection
- **[Recommendations](../recommendations.md)** - Find optimization opportunities

---

**Need Help?**
- Check [Cloud Accounts Documentation](../cloud-accounts.md)
- Review [Troubleshooting Guide](../troubleshooting.md)
- Check backend logs: `docker-compose logs -f backend`
