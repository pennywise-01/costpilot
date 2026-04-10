# Schedulers

![Schedulers Page](screenshots/schedulers-page.png)

Automate data collection, processing, and scheduled tasks.

---

## Overview

Schedulers automate repetitive tasks like expense collection, resource discovery, recommendation generation, and custom jobs. They provide reliable, monitored automation with failure handling and dead letter queues.

**URL**: `/schedulers`

**Key Features:**
- Automated data collection schedulers
- Interval-based and cron-based scheduling
- Enable/disable toggle
- Manual trigger with overrides
- Run history with status tracking
- Run logs with filtering
- Dead letter queue for failed jobs
- Organization-level statistics dashboard

---

## Page Layout

### Scheduler Statistics

At the top, summary statistics:

- **Total Schedulers**: Number of schedulers
- **Active Schedulers**: Number of enabled schedulers
- **Recent Runs**: Runs in last 24 hours
- **Failed Runs**: Recent failures
- **Dead Letter Queue**: Jobs awaiting retry

---

### Schedulers List

The main table displays all schedulers:

**Columns:**
- **Name**: Scheduler name (clickable to view details)
- **Description**: Brief explanation
- **Schedule Type**: Interval, Cron, or Once
- **Schedule**: Interval (minutes) or cron expression
- **Data Types**: What data is collected (Expenses, Resources, Recommendations)
- **Status**: Enabled or Disabled
- **Last Run**: Most recent execution time
- **Last Run Status**: Success, Failed, Running
- **Next Run**: Scheduled next execution time
- **Actions**: Edit, Enable/Disable, Trigger, Delete

---

## Schedule Types

### Interval

Runs every N minutes.

**Example:**
- Schedule Type: `interval`
- Interval: 60 (minutes)
- Runs every 60 minutes

**Use Cases:**
- Expense collection (hourly)
- Resource discovery (every 2 hours)
- Recommendation generation (every 4 hours)

---

### Cron

Runs at specific times using cron expressions.

**Example:**
- Schedule Type: `cron`
- Cron Expression: `0 2 * * *` (daily at 2 AM)
- Runs daily at 2:00 AM

**Common Expressions:**
- `0 */6 * * *`: Every 6 hours
- `0 0 * * 0`: Weekly on Sunday at midnight
- `0 9 * * 1-5`: Weekdays at 9 AM
- `0 0 1 * *`: First of every month

**Use Cases:**
- Daily reports
- Weekly cleanup
- Monthly billing data collection

---

### Once

One-time execution at a specified time.

**Use Cases:**
- One-time data backfill
- Manual migration
- Ad-hoc analysis

---

## Data Types

Schedulers can collect one or more data types:

| Data Type | Description | Typical Frequency |
|-----------|-------------|-------------------|
| **Expenses** | Cost data from cloud providers | Every 1-6 hours |
| **Resources** | Resource inventory and metadata | Every 2-6 hours |
| **Recommendations** | Optimization recommendations | Every 4-12 hours |

---

## Creating a Scheduler

### Via API

```
POST /api/v1/organizations/{org_id}/schedulers
```

**Request Body:**
```json
{
  "name": "Expense Collection",
  "description": "Collect expense data from all cloud accounts every hour",
  "schedule_type": "interval",
  "interval_minutes": 60,
  "data_types": ["expenses"],
  "enabled": true
}
```

**Cron Example:**
```json
{
  "name": "Daily Resource Discovery",
  "description": "Discover resources daily at 2 AM",
  "schedule_type": "cron",
  "cron_expression": "0 2 * * *",
  "timezone": "UTC",
  "data_types": ["resources"],
  "enabled": true
}
```

---

## Managing Schedulers

### Enable/Disable

**From List:**
1. Click the **Enable/Disable** toggle
2. Enabling schedules the next run
3. Disabling cancels scheduled runs

**Effect:**
- Disabled schedulers don't execute
- Existing run history is preserved
- Re-enabling resumes scheduling

---

### Manual Trigger

**From List:**
1. Click **"Trigger"** button
2. Scheduler runs immediately
3. Optional: Override data types for this run

**Use Cases:**
- Test scheduler functionality
- Backfill missing data
- Run on-demand outside schedule

---

### Edit a Scheduler

1. Click on scheduler name
2. Click **"Edit"**
3. Modify any field (name, schedule, data types)
4. Click **"Save"**

**Note**: Changing schedule recalculates next run time.

---

### Delete a Scheduler

1. Click on scheduler name
2. Click **"Delete"**
3. Confirm deletion

**Effect:**
- Scheduler is removed
- Scheduled runs are cancelled
- Run history is preserved

---

## Scheduler Detail Page

Click on a scheduler name to view:

### Overview
- Name and description
- Schedule configuration
- Data types
- Enabled status
- Creator and created date

### Statistics
- Total runs
- Successful runs
- Failed runs
- Average duration
- Consecutive failures

### Run History

Table of recent runs:

**Columns:**
- **Run ID**: Unique identifier
- **Status**: Pending, Running, Completed, Failed, Cancelled, Partial
- **Started At**: Run start timestamp
- **Ended At**: Run end timestamp
- **Duration**: How long the run took
- **Data Types**: What was collected
- **Actions**: View logs, retry

---

### Run Logs

View detailed execution logs:

**Filters:**
- **Log Level**: Debug, Info, Warning, Error
- **Data Type**: Filter by data type being processed
- **Search**: Search log messages

**Log Entries:**
- Timestamp
- Level (DEBUG, INFO, WARNING, ERROR)
- Message
- Data type (if applicable)

---

## Dead Letter Queue

When a scheduler run fails repeatedly, it moves to the Dead Letter Queue (DLQ) for manual intervention.

### Viewing DLQ

1. Navigate to **Schedulers** page
2. Click **"Dead Letter Queue"** tab
3. See failed jobs with:
   - Job ID
   - Scheduler name
   - Failure reason
   - Consecutive failures
   - Failed at timestamp

---

### Retry a Dead Letter Job

1. Click **"Retry"** on the job
2. Job is requeued for execution
3. If successful, removed from DLQ
4. If fails again, returns to DLQ

---

### Abandon a Dead Letter Job

1. Click **"Abandon"** on the job
2. Job is permanently removed from DLQ
3. Use when job is no longer relevant

---

## Organization Scheduler Statistics

View aggregate statistics across all schedulers:

```
GET /api/v1/organizations/{org_id}/scheduler-stats
```

**Response:**
```json
{
  "total_schedulers": 5,
  "active_schedulers": 3,
  "total_runs_24h": 48,
  "successful_runs_24h": 46,
  "failed_runs_24h": 2,
  "average_duration_seconds": 120,
  "dead_letter_queue_size": 1
}
```

---

## API Endpoints

### Create Scheduler
```
POST /api/v1/organizations/{org_id}/schedulers
```

### List Schedulers
```
GET /api/v1/organizations/{org_id}/schedulers
```

### Get Single Scheduler
```
GET /api/v1/organizations/{org_id}/schedulers/{scheduler_id}
```

### Update Scheduler
```
PATCH /api/v1/organizations/{org_id}/schedulers/{scheduler_id}
```

### Delete Scheduler
```
DELETE /api/v1/organizations/{org_id}/schedulers/{scheduler_id}
```

### Toggle Enable/Disable
```
POST /api/v1/organizations/{org_id}/schedulers/{scheduler_id}/toggle
```

### Manual Trigger
```
POST /api/v1/organizations/{org_id}/schedulers/{scheduler_id}/trigger
```

### Get Statistics
```
GET /api/v1/organizations/{org_id}/schedulers/{scheduler_id}/stats
```

### Get Run History
```
GET /api/v1/organizations/{org_id}/schedulers/{scheduler_id}/runs?skip=0&limit=20&status=
```

### Get Run Detail
```
GET /api/v1/organizations/{org_id}/schedulers/{scheduler_id}/runs/{run_id}
```

### Get Run Logs
```
GET /api/v1/organizations/{org_id}/schedulers/{scheduler_id}/runs/{run_id}/logs
```

### Organization Stats
```
GET /api/v1/organizations/{org_id}/scheduler-stats
```

### Dead Letter Queue
```
GET /api/v1/organizations/{org_id}/dead-letter
POST /api/v1/organizations/{org_id}/dead-letter/{job_id}/retry
DELETE /api/v1/organizations/{org_id}/dead-letter/{job_id}
```

---

## Best Practices

### Scheduler Design

1. **One Task Per Scheduler**: Each scheduler should do one thing
2. **Appropriate Frequency**: Don't over-collect (costly) or under-collect (stale data)
3. **Descriptive Names**: Include purpose and frequency in name
4. **Monitor Failures**: Watch for consecutive failures
5. **Test First**: Manually trigger before enabling schedule

### Recommended Frequencies

| Data Type | Recommended Frequency | Notes |
|-----------|----------------------|-------|
| Expenses | 1-6 hours | Balance freshness vs API costs |
| Resources | 2-6 hours | Resources change infrequently |
| Recommendations | 4-12 hours | Recommendations don't need to be real-time |

### Failure Handling

1. **Set Alerts**: Monitor for scheduler failures
2. **Check DLQ**: Review dead letter queue daily
3. **Retry Promptly**: Retry failed jobs after fixing root cause
4. **Abandon Old Jobs**: Clean up jobs no longer relevant
5. **Review Logs**: Check logs to understand failures

---

## Troubleshooting

### Scheduler Not Running

**Check:**
1. Scheduler is enabled
2. Schedule configuration is correct
3. APScheduler service is running
4. Backend logs for errors

**Solution:**
- Manually trigger to test
- Review scheduler logs
- Restart backend if needed

### Scheduler Runs But Collects No Data

**Possible Causes:**
1. No cloud accounts connected
2. Cloud account API errors
3. No costs/resources exist yet
4. Filters too restrictive

**Check:**
1. Cloud accounts are healthy
2. Cloud provider consoles show data
3. Scheduler run logs for errors
4. Data type configuration

### Frequent Failures

**Check:**
1. Cloud provider rate limiting
2. Timeout errors (increase timeout if needed)
3. Authentication/credential issues
4. Backend resource constraints

**Solutions:**
- Reduce scheduler frequency
- Implement retry logic (built-in)
- Check cloud provider status
- Review backend logs

---

## Next Steps

- **[Dashboard](dashboard.md)** - View collected cost data
- **[Expenses](expenses.md)** - Analyze expense data
- **[Resources](resources.md)** - View discovered resources
- **[Notifications](notifications.md)** - Alert on scheduler failures

---

**Related Documentation:**
- [How to Set Up Schedulers](guides/setup-schedulers.md)
- [API Reference](api-reference.md)
