# How to Export Data

Create, manage, and download export jobs for cost reports and data analysis.

---

## Overview

Export data from CostPilot in various formats (CSV, JSON, Excel, PDF, Parquet) for reporting, analysis, and archival purposes.

**Time Required:** 5-10 minutes per export  
**Prerequisites:**
- Data exists in system (cloud accounts connected, data collected)
- Engineer, Billing Admin, or Organization Admin role

---

## Common Export Scenarios

| Scenario | Data Type | Format | Use Case |
|----------|-----------|--------|----------|
| Monthly Cost Report | Expenses | Excel | Finance team review |
| Resource Inventory | Resources | CSV | Asset management |
| Recommendation Summary | Recommendations | PDF | Leadership presentation |
| Cost Analysis | Expenses | JSON | Data analysis |
| Audit Trail | Activity Logs | CSV | Compliance |
| User Access Report | Users | Excel | Security audit |

---

## Exporting Expense Data

### Step 1: Navigate to Exports

1. Click **"Exports"** in left sidebar
2. Click **"Create Export"** button

---

### Step 2: Configure Export

**Job Name:**
- Enter descriptive name
- Example: `April 2026 Expense Report`

**Data Type:**
- Select **Expenses**

**Format:**
- Select **Excel** (recommended for finance reports)
- Or **CSV** for data analysis
- Or **PDF** for human-readable reports

---

**Date Range:**
- **Start Date**: `2026-04-01`
- **End Date**: `2026-04-30`

---

**Filters (Optional):**
- Filter by cloud type (AWS, Azure, GCP)
- Filter by pool
- Filter by owner
- Leave blank for all data

---

**Columns (Optional):**
- Select specific columns
- Or leave blank for all columns
- Common columns: date, cloud_type, service, resource_name, cost, pool

---

**Grouping & Sorting:**
- **Group by**: `cloud_type` (group costs by provider)
- **Sort by**: `cost` descending (highest costs first)

---

### Step 3: Preview Export

1. Click **"Preview"** (if available)
2. Review first 100 rows
3. Verify columns and data look correct
4. Adjust filters if needed

---

### Step 4: Create Export Job

1. Click **"Create Export"**
2. Job is queued for processing
3. Status shows as **"Pending"**

---

### Step 5: Wait for Processing

Processing time depends on data volume:
- Small exports (< 10,000 rows): 1-2 minutes
- Medium exports (10,000-100,000 rows): 5-10 minutes
- Large exports (> 100,000 rows): 10-30 minutes

---

### Step 6: Download Export

1. Status changes to **"Completed"**
2. Click **"Download"** button
3. File download begins
4. Save file to desired location

**Note:** Download link expires after 15 minutes. Download promptly.

---

## Creating Export Templates

Save export configurations for reuse.

### Step 1: Configure Export

Set up export as usual (data type, format, filters, columns, etc.)

---

### Step 2: Save as Template

1. Before creating job, click **"Save as Template"**
2. Enter template name: `Monthly Expense Report`
3. Enter description: `Excel expense report for finance team, all clouds`
4. Click **"Save"**

---

### Step 3: Use Template

1. Click **"Create from Template"**
2. Select `Monthly Expense Report` template
3. Adjust date range for current month
4. Create and execute export

**Benefit:** Saves time for recurring reports.

---

## Scheduling Recurring Exports

Automate regular exports.

### Step 1: Navigate to Scheduled Exports

1. Go to **Exports** page
2. Click **"Scheduled Exports"** tab
3. Click **"Create Scheduled Export"**

---

### Step 2: Configure Schedule

**Export Configuration:**
- Set up same as one-time export

**Schedule:**
- Select **Cron** schedule type
- Enter cron expression

**Common Schedules:**
- `0 9 1 * *`: 1st of every month at 9 AM
- `0 9 * * 1`: Every Monday at 9 AM
- `0 8 * * *`: Daily at 8 AM

**Timezone:**
- Select your timezone (e.g., `UTC`, `America/New_York`)

**Delivery Method:**
- **Download**: Manual download
- **Email**: Send to email addresses
- **S3/GCS/Azure**: Upload to cloud storage

---

### Step 3: Create Scheduled Export

1. Click **"Create"**
2. Export runs automatically on schedule
3. Manage from Scheduled Exports tab

---

## Export Formats Explained

### CSV (Comma-Separated Values)

**Best For:**
- Spreadsheet import (Excel, Google Sheets)
- Data analysis tools
- Programmatic processing

**Pros:**
- Universal compatibility
- Easy to parse
- Small file size

**Cons:**
- No formatting
- Single sheet only
- No formulas

---

### Excel (.xlsx)

**Best For:**
- Finance reports
- Multi-sheet exports
- Formatted reports

**Pros:**
- Multiple sheets
- Formatting support
- Formulas and charts

**Cons:**
- Larger file size
- Requires Excel or compatible software

---

### JSON

**Best For:**
- API integration
- Programmatic processing
- Data pipelines

**Pros:**
- Structured data
- Easy to parse programmatically
- Schema-preserving

**Cons:**
- Not human-readable at scale
- Not spreadsheet-compatible

---

### PDF

**Best For:**
- Human-readable reports
- Presentations
- Archival

**Pros:**
- Formatted layout
- Consistent across devices
- Print-ready

**Cons:**
- Not easily editable
- Larger file size
- Not machine-parseable

---

### Parquet

**Best For:**
- Big data analytics
- Columnar queries
- Data lakes

**Pros:**
- Highly compressed
- Columnar format
- Fast analytics queries

**Cons:**
- Requires specialized tools
- Not human-readable
- Not spreadsheet-compatible

---

## Best Practices

### Export Management

1. **Use Templates**: Save recurring export configurations
2. **Schedule Reports**: Automate monthly/weekly exports
3. **Name Clearly**: Include date range in export name
4. **Download Promptly**: Download before link expires (15 min)
5. **Store Securely**: Exported files may contain sensitive data

### Data Selection

1. **Limit Date Range**: Export only needed dates
2. **Filter Appropriately**: Narrow to relevant data
3. **Select Columns**: Export only needed columns
4. **Group Logically**: Group by meaningful fields

### File Management

1. **Organize by Date**: Save files with date in name
   - Example: `expenses_2026-04.xlsx`
2. **Version Control**: Keep historical exports
3. **Archive Old Files**: Move old exports to archive storage
4. **Delete Local Copies**: Remove sensitive files when done

---

## Troubleshooting

### Export Job Fails

**Check:**
1. Date range is not too large (try smaller range)
2. Filters are valid
3. Backend has sufficient memory
4. No cloud provider API errors

**Solutions:**
1. Reduce date range
2. Simplify filters
3. Retry job
4. Use streaming export for very large datasets

---

### Download Link Expired

**Token Expiry:** 15 minutes

**Solution:**
1. Go back to export job
2. Click **"Download"** again
3. New token is generated
4. Download immediately

---

### Export File Too Large

**Solutions:**
1. Reduce date range
2. Add more filters (specific pool, cloud type, etc.)
3. Select fewer columns
4. Use Parquet format (highly compressed)
5. Use streaming export

---

### No Data in Export

**Check:**
1. Date range has data
2. Filters aren't too restrictive
3. Data type is correct
4. Cloud accounts are connected and healthy

**Solutions:**
1. Expand date range
2. Remove filters
3. Verify data exists in CostPilot first
4. Check schedulers have run

---

### Export Takes Too Long

**For Large Datasets:**
1. Use streaming export endpoint
2. Export in smaller chunks (by month, by pool)
3. Run during off-peak hours
4. Consider Parquet format for efficiency

---

## API Reference

### Create Export Job

```
POST /api/v1/enterprise/organizations/{org_id}/exports
```

**Request Body:**
```json
{
  "name": "April 2026 Expenses",
  "data_type": "expenses",
  "format": "excel",
  "start_date": "2026-04-01",
  "end_date": "2026-04-30",
  "filters": {
    "cloud_type": "aws"
  },
  "columns": ["date", "service", "resource_name", "cost"],
  "group_by": "service",
  "sort_by": "cost",
  "sort_order": "desc"
}
```

---

### Execute Export Job

```
POST /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/execute
```

---

### Get Download URL

```
GET /api/v1/enterprise/organizations/{org_id}/exports/{job_id}/download
```

**Response:**
```json
{
  "download_url": "/api/v1/enterprise/organizations/{org_id}/exports/{job_id}/file?download_token=abc123",
  "expires_at": "2026-04-09T12:15:00Z"
}
```

---

### Create Export Template

```
POST /api/v1/enterprise/organizations/{org_id}/export-templates
```

**Request Body:**
```json
{
  "name": "Monthly Expense Report",
  "description": "Excel expense report for finance team",
  "data_type": "expenses",
  "format": "excel",
  "columns": ["date", "cloud_type", "service", "cost", "pool"],
  "group_by": "cloud_type",
  "sort_by": "cost",
  "sort_order": "desc"
}
```

---

## Next Steps

After exporting data:

- **[Expenses](../expenses.md)** - Analyze exported cost data
- **[Dashboard](../dashboard.md)** - Review summary metrics
- **[Schedulers](../schedulers.md)** - Schedule recurring exports
- **[Notifications](../notifications.md)** - Get notified when exports complete

---

**Need Help?**
- Check [Exports Documentation](../exports.md)
- Review [API Reference](../api-reference.md)
- Check backend logs: `docker-compose logs -f backend`
