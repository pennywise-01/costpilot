# Data Export

![Exports Page](screenshots/exports-page.png)

Export, download, and schedule cost data reports.

---

## Overview

The Data Export feature allows you to create, manage, and download export jobs for cost data, resources, recommendations, and more. Support multiple formats and delivery methods.

**URL**: `/exports`

**Key Features:**
- Multiple export formats (CSV, JSON, Parquet, PDF, Excel)
- Multiple data types (Expenses, Resources, Recommendations, etc.)
- Export templates for reusable configurations
- Scheduled exports for recurring reports
- Streaming export for large datasets
- Export preview before creating full job
- Secure signed download tokens
- Multiple delivery methods (Download, S3, GCS, Azure Blob, Email, SFTP)

---

## Page Layout

### Export Jobs List

The main page displays all export jobs:

**Columns:**
- **Job Name**: Export job name (clickable to view details)
- **Data Type**: Expenses, Resources, Recommendations, etc.
- **Format**: CSV, JSON, Parquet, PDF, Excel
- **Status**: Pending, Running, Completed, Failed
- **Created By**: User who created the job
- **Created At**: Job creation timestamp
- **File Size**: Size of export file (when completed)
- **Actions**: Download, Preview, Delete

**Filters:**
- Data type
- Status
- Date range
- Created by

---

## Creating an Export Job

### Step 1: Click Create Export

- Navigate to **Exports** page
- Click **"Create Export"** button

---

### Step 2: Configure Export

**Job Name:**
- Descriptive name for this export
- Example: "April 2026 Expense Report"

**Data Type:**
Select what to export:
- **Expenses**: Cost line items
- **Resources**: Resource inventory
- **Recommendations**: Optimization recommendations
- **Cloud Accounts**: Connected cloud accounts
- **Pools**: Budget pool hierarchy
- **Users**: User list and roles
- **Activity Logs**: Organization activity
- **Scheduler Runs**: Scheduler execution history

---

**Format:**
Select output format:
- **CSV**: Comma-separated values (spreadsheet compatible)
- **JSON**: JSON array of objects
- **Parquet**: Columnar format (big data)
- **PDF**: Formatted report (human-readable)
- **Excel**: Excel workbook with multiple sheets

---

**Date Range:**
- Start date and end date (for time-based data types)
- Leave blank for all-time data

---

**Filters:**
- Apply filters to narrow down data
- Examples:
  - Filter by cloud type (AWS, Azure, GCP)
  - Filter by pool
  - Filter by owner
  - Filter by resource type

---

**Columns:**
- Select which columns to include
- Leave blank for all columns
- Choose specific columns for focused exports

**View Available Columns:**
```
GET /api/v1/enterprise/organizations/{org_id}/export-columns/{data_type}
```

---

**Grouping & Sorting:**
- Group by: Organize rows by field (e.g., group expenses by cloud)
- Sort by: Order rows by field (e.g., sort by cost descending)

---

### Step 3: Create Job

- Click **"Create Export"**
- Job is queued for processing
- Status shows as "Pending"

---

## Executing an Export

### Automatic Execution

- Jobs are processed automatically by scheduler
- Status changes: Pending → Running → Completed

---

### Manual Execution

1. Select the job
2. Click **"Execute"**
3. Job runs immediately
4. Monitor status and progress

```
POST /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/execute
```

---

## Downloading an Export

### Get Download URL

1. Wait for job status to be "Completed"
2. Click **"Download"** button
3. Backend generates signed download token (15-min expiry)
4. File download begins

---

### Download API

```
GET /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/download
```

**Response:**
```json
{
  "download_url": "/api/v1/enterprise/organizations/{org_id}/exports/{job_id}/file?download_token=<signed-token>",
  "expires_at": "2026-04-09T12:15:00Z"
}
```

**Download File:**
```
GET /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/file?download_token=<token>
```

**Security:**
- Download tokens are HMAC-SHA256 signed
- 15-minute expiry
- Path traversal prevention
- Audit logged

---

## Export Templates

Save export configurations for reuse.

### Creating a Template

1. Configure an export job with desired settings
2. Before creating, click **"Save as Template"**
3. Enter template name and description
4. Template is saved for future use

---

### Using a Template

1. Click **"Create from Template"**
2. Select template from list
3. Job is pre-configured with template settings
4. Adjust date range if needed
5. Create and execute job

---

### Managing Templates

**List Templates:**
```
GET /api/v1/enterprise/organizations/{org_id}/export-templates?data_type=
```

**Get Template:**
```
GET /api/v1/enterprise/organizations/{org_id}/export-templates/{template_id}
```

**Update Template:**
```
PATCH /api/v1/enterprise/organizations/{org_id}/export-templates/{template_id}
```

**Delete Template:**
```
DELETE /api/v1/enterprise/organizations/{org_id}/export-templates/{template_id}
```

---

## Scheduled Exports

Recurring exports at scheduled intervals.

### Creating a Scheduled Export

1. Navigate to **Exports** page
2. Click **"Scheduled Exports"** tab
3. Click **"Create Scheduled Export"**
4. Configure:
   - Export configuration (same as one-time export)
   - Schedule: Cron expression
   - Timezone: For schedule interpretation
   - Delivery method: Download, S3, GCS, Email, etc.
5. Click **"Create"**

---

### Example: Monthly Expense Report

```
Name: Monthly Expense Report
Data Type: Expenses
Format: Excel
Schedule: 0 9 1 * * (1st of every month at 9 AM)
Timezone: UTC
Delivery: Email to finance team
```

---

### Managing Scheduled Exports

**List:**
```
GET /api/v1/enterprise/organizations/{org_id}/scheduled-exports
```

**Update:**
```
PATCH /api/v1/enterprise/organizations/{org_id}/scheduled-exports/{scheduled_id}
```

**Delete:**
```
DELETE /api/v1/enterprise/organizations/{org_id}/scheduled-exports/{scheduled_id}
```

---

## Streaming Export

For large datasets, use streaming export to avoid loading everything into memory.

```
GET /api/v1/enterprise/organizations/{org_id}/exports/stream?data_type=expenses&format=csv
```

**Response:**
- Streams CSV/JSON data directly to client
- No intermediate file storage
- Suitable for very large exports

---

## Export Preview

Preview export data before creating full job.

```
POST /api/v1/enterprise/organizations/{org_id}/export-preview
```

**Request Body:**
```json
{
  "data_type": "expenses",
  "format": "csv",
  "start_date": "2026-04-01",
  "end_date": "2026-04-09",
  "filters": {"cloud_type": "aws"},
  "limit": 100
}
```

**Response:**
- First 100 rows of data
- Verify columns and filters are correct
- Then create full export job

---

## Delivery Methods

### Direct Download
- Default method
- Download via signed URL
- File stored temporarily

### S3
- Upload to AWS S3 bucket
- Configure bucket and prefix
- Requires AWS credentials

### GCS
- Upload to Google Cloud Storage
- Configure bucket and prefix
- Requires GCP credentials

### Azure Blob
- Upload to Azure Blob Storage
- Configure container and prefix
- Requires Azure credentials

### Email
- Send as email attachment
- Configure recipient email addresses
- File attached to email

### SFTP
- Upload to SFTP server
- Configure server, path, credentials
- Requires SFTP credentials

---

## API Endpoints

### Export Templates
```
POST /api/v1/enterprise/organizations/{org_id}/export-templates
GET /api/v1/enterprise/organizations/{org_id}/export-templates
GET /api/v1/enterprise/organizations/{org_id}/export-templates/{template_id}
PATCH /api/v1/enterprise/organizations/{org_id}/export-templates/{template_id}
DELETE /api/v1/enterprise/organizations/{org_id}/export-templates/{template_id}
```

### Export Jobs
```
POST /api/v1/enterprise/organizations/{org_id}/exports
GET /api/v1/enterprise/organizations/{org_id}/exports
GET /api/v1/enterprise/organizations/{org_id}/exports/{job_id}
POST /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/execute
GET /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/download
GET /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/file?download_token=
```

### Streaming Export
```
GET /api/v1/enterprise/organizations/{org_id}/exports/stream?data_type=&format=
```

### Scheduled Exports
```
POST /api/v1/enterprise/organizations/{org_id}/scheduled-exports
GET /api/v1/enterprise/organizations/{org_id}/scheduled-exports
PATCH /api/v1/enterprise/organizations/{org_id}/scheduled-exports/{scheduled_id}
DELETE /api/v1/enterprise/organizations/{org_id}/scheduled-exports/{scheduled_id}
```

### Available Columns
```
GET /api/v1/enterprise/organizations/{org_id}/export-columns/{data_type}
```

### Export Preview
```
POST /api/v1/enterprise/organizations/{org_id}/export-preview
```

---

## Best Practices

### Export Management

1. **Use Templates**: Save recurring export configurations
2. **Schedule Reports**: Automate monthly/weekly reports
3. **Preview First**: Always preview before creating large exports
4. **Choose Right Format**: CSV for spreadsheets, JSON for APIs, Parquet for analytics
5. **Delete Old Jobs**: Clean up completed/failed jobs regularly

### Data Selection

1. **Limit Date Range**: Export only needed date ranges
2. **Filter Appropriately**: Narrow down data to relevant subset
3. **Select Columns**: Export only needed columns to reduce file size
4. **Group Logically**: Group by meaningful fields for readability

### Security

1. **Download Promptly**: Download files before token expires (15 min)
2. **Secure Storage**: Store exported files securely
3. **Audit Access**: Review export audit logs
4. **Limit Formats**: Don't export sensitive data in PDF (easily shared)

---

## Troubleshooting

### Export Job Fails

**Check:**
1. Date range is not too large
2. Filters are valid
3. Backend has sufficient memory
4. Cloud provider APIs are accessible

**Solutions:**
1. Reduce date range
2. Simplify filters
3. Use streaming export
4. Retry job

### Download Link Expired

**Token Expiry**: 15 minutes

**Solution:**
1. Request new download URL
2. Download immediately

### Export File Too Large

**Solutions:**
1. Reduce date range
2. Add more filters
3. Select fewer columns
4. Use Parquet format (compressed)
5. Use streaming export

### No Data in Export

**Check:**
1. Date range has data
2. Filters aren't too restrictive
3. Data type is correct
4. Cloud accounts are connected

---

## Next Steps

- **[Expenses](expenses.md)** - Export cost data
- **[Resources](resources.md)** - Export resource inventory
- **[Schedulers](schedulers.md)** - Schedule recurring exports
- **[Dashboard](dashboard.md)** - View data before exporting

---

**Related Documentation:**
- [How to Export Data](guides/export-data.md)
- [API Reference](api-reference.md)
