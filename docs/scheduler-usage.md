# Scheduler Feature Usage Guide

## Overview

The Scheduler feature allows you to configure automated data collection from Cloud Service Providers (CSP) on a schedule. You can create multiple schedulers, each configured to collect specific data types (expenses, resources, recommendations) at different intervals.

## Features

### Schedule Types

1. **Interval**: Run every X minutes/hours
   - Options: 5 min, 15 min, 30 min, 1 hour, 6 hours, 12 hours, 1 day, 1 week
   - Best for: Regular data synchronization

2. **Cron**: Flexible cron expressions
   - Examples: Every hour (`0 * * * *`), Weekdays at 9 AM (`0 9 * * 1-5`)
   - Best for: Complex schedules, business hours only

3. **One-time**: Run once at a specific date/time
   - Best for: Initial data seeding or one-off imports

### Data Types

Each scheduler can be configured to collect:

- **Expenses**: Cost and billing data from CSP APIs
  - Monthly cost summaries
  - Daily cost breakdowns
  - Service-level cost analysis

- **Resources**: Cloud resource inventory
  - EC2 instances, RDS databases, S3 buckets (AWS)
  - Virtual machines, storage accounts (Azure)
  - Compute instances, Cloud Storage (GCP)

- **Recommendations**: Cost optimization recommendations
  - AWS Cost Explorer recommendations
  - Azure Advisor recommendations
  - GCP Recommender API suggestions

## Getting Started

### 1. Access the Schedulers Page

Navigate to **Home → Schedulers** in the left sidebar menu.

### 2. Create Your First Scheduler

1. Click **"Create Scheduler"** button
2. Fill in the configuration form:
   - **Name**: A descriptive name (e.g., "Daily Morning Sync")
   - **Description**: Optional details about the scheduler's purpose
   - **Data Types**: Select which data types to collect
   - **Schedule Type**: Choose interval, cron, or one-time
   - **Timing**: Set the schedule parameters
   - **Timezone**: Select your preferred timezone
3. Click **"Create Scheduler"**

### 3. Enable the Scheduler

New schedulers are enabled by default. Use the toggle switch to enable/disable.

### 4. Monitor Execution

- View run history in the **"View Runs"** modal
- Check execution logs for debugging
- Monitor statistics on the main page

## Managing Schedulers

### Edit a Scheduler

1. Click the **Edit** (pencil) icon on any scheduler row
2. Modify the configuration
3. Click **"Update Scheduler"**

### Manual Trigger

Click the **Play** icon to manually trigger a scheduler run immediately. Useful for testing or when you need fresh data outside the normal schedule.

### Enable/Disable

Use the toggle switch to temporarily disable a scheduler without deleting it.

### Delete a Scheduler

Click the **Delete** (trash) icon to permanently remove a scheduler. This will also delete all associated run history and logs.

## Understanding Run Status

| Status | Description |
|--------|-------------|
| **Pending** | Run is queued and waiting to start |
| **Running** | Currently executing |
| **Completed** | All data types collected successfully |
| **Failed** | All data types failed to collect |
| **Partial** | Some data types succeeded, others failed |
| **Cancelled** | Run was cancelled before completion |

## Troubleshooting

### Scheduler Not Running

1. Check if scheduler is **enabled**
2. Verify schedule configuration (start/end dates)
3. Check for **consecutive failures** - scheduler auto-disables after threshold

### Data Collection Failures

1. Check **logs** in the run details
2. Verify cloud account credentials are valid
3. Check CSP API rate limits
4. Review error messages for specific issues

### Viewing Logs

1. Click **"View Runs"** on any scheduler
2. Click **"View Logs"** on any run
3. Filter by log level (debug, info, warning, error)
4. Filter by data type (expenses, resources, recommendations)

## Best Practices

### Scheduling Recommendations

- **Expenses**: Collect daily or twice daily (billing data updates periodically)
- **Resources**: Collect hourly or every 6 hours for active monitoring
- **Recommendations**: Collect daily (recommendations don't change frequently)

### Performance Considerations

- Avoid scheduling multiple large data collections simultaneously
- Use longer intervals for resource-heavy collections
- Monitor API rate limits from your CSPs

### Security

- Schedulers run with the permissions of the user who created them
- Ensure cloud account credentials have appropriate read-only access
- Regularly rotate credentials

## API Reference

### Create Scheduler

```http
POST /api/v1/organizations/{org_id}/schedulers
Content-Type: application/json

{
  "name": "Hourly Resource Sync",
  "description": "Sync resources every hour",
  "collect_expenses": false,
  "collect_resources": true,
  "collect_recommendations": false,
  "schedule_type": "interval",
  "interval_minutes": 60,
  "timezone": "UTC"
}
```

### List Schedulers

```http
GET /api/v1/organizations/{org_id}/schedulers
```

### Trigger Manually

```http
POST /api/v1/organizations/{org_id}/schedulers/{id}/trigger
```

### Get Run History

```http
GET /api/v1/organizations/{org_id}/schedulers/{id}/runs
```

### Get Run Logs

```http
GET /api/v1/organizations/{org_id}/schedulers/{id}/runs/{run_id}/logs
```

## Database Schema

### scheduler_configs

Stores scheduler configurations:
- `id`: Unique identifier
- `organization_id`: Owning organization
- `name`, `description`: Human-readable info
- `collect_*`: Boolean flags for data types
- `schedule_type`: interval, cron, or once
- `interval_minutes` / `cron_expression`: Schedule details
- `is_enabled`: Active status
- `consecutive_failures`: Failure tracking
- `created_by`, `created_at`: Audit fields

### scheduler_runs

Tracks each execution:
- `id`: Unique identifier
- `scheduler_config_id`: Parent scheduler
- `status`: pending, running, completed, failed, partial
- `started_at`, `completed_at`, `duration_seconds`: Timing
- `collected_*`: What was collected
- `*_records`: Count of records per type
- `error_message`, `error_details`: Failure info
- `trigger_type`: scheduled, manual, or api

### scheduler_logs

Detailed execution logs:
- `id`: Unique identifier
- `scheduler_run_id`: Parent run
- `level`: debug, info, warning, error
- `message`: Log message
- `data_type`: Which data type (expenses, resources, recommendations)
- `details`: Additional structured data

## Advanced Configuration

### Cron Expression Examples

```
Every minute:        * * * * *
Every hour:          0 * * * *
Every 6 hours:       0 */6 * * *
Daily at midnight:   0 0 * * *
Weekdays at 9 AM:    0 9 * * 1-5
Weekly on Sunday:    0 0 * * 0
Monthly on 1st:      0 0 1 * *
```

### Max Consecutive Failures

Set this to automatically disable schedulers that consistently fail:
- `3` (default): Good balance of retry vs. auto-disable
- `1`: Aggressive - disable on first failure
- `10`: Lenient - allow many retries

## Support

For issues or questions about the scheduler feature:
1. Check the run logs for detailed error messages
2. Verify CSP credentials are valid
3. Review API rate limits from your cloud provider
4. Contact support with scheduler ID and run ID for investigation
