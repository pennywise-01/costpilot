# Expense Tracking (Cost Explorer)

![Expenses Page](screenshots/expenses-page.png)

Analyze your cloud costs with detailed breakdowns, trends, and comparisons.

---

## Overview

The Expenses page (Cost Explorer) provides powerful cost analysis capabilities with multiple views, breakdowns, and period-over-period comparisons.

**URL**: `/expenses`

**Key Features:**
- Cost trends over custom date ranges
- Breakdown by Total, Cloud Provider, Pool, or Owner
- Stacked bar charts for visual analysis
- Period-over-period comparison with change percentages
- Daily averages calculation
- Cached data with graceful degradation

**As shown in the screenshot above:**
- Total expenses amount displayed prominently ($12,847 in example)
- Cost breakdown chart showing expenses over time
- Date range picker for filtering
- Period comparison metrics
- Detailed cost table with breakdown

---

## Page Layout

### Date Range Picker

At the top of the page, select your analysis period:

**Presets:**
- Last 7 days
- Last 30 days
- Last 90 days
- This month
- Last month
- Custom range

**Custom Range:**
- Click **"Custom"**
- Select start date and end date
- Click **"Apply"**

**Note**: Data is only available from the date your first cloud account was connected.

---

### Cost Trend Chart

![Cost Trend Chart](screenshots/expenses-page.png)

The main chart shows daily costs over the selected date range.

**View Modes:**
- **Total**: Combined cost across all cloud providers
- **By Cloud**: Stacked bars showing AWS, Azure, GCP breakdown
- **By Pool**: Stacked bars showing budget pool breakdown
- **By Owner**: Stacked bars showing cost by resource owner

**Interactions:**
- **Hover**: See exact daily cost in tooltip
- **Zoom**: Select region to zoom in (if enabled)
- **Toggle Legend**: Click legend items to show/hide series

---

### Summary Metrics

Below the chart, key metrics are displayed:

**Current Period:**
- **Total Cost**: Sum of costs for selected range
- **Daily Average**: Total cost / number of days
- **Day-over-Day Change**: Percentage change from previous day

**Comparison with Previous Period:**
- **Previous Period Total**: Cost for equivalent prior period
- **Change %**: Percentage increase/decrease
- **Change Amount**: Absolute difference in cost

---

### Period-over-Period Comparison Table

Detailed day-by-day breakdown:

**Columns:**
- **Date**: The day being analyzed
- **Current Period Cost**: Cost for that day
- **Previous Period Cost**: Cost for same day in prior period
- **Change %**: Percentage change
- **Change Amount**: Absolute difference
- **Current Daily Avg**: Running daily average
- **Previous Daily Avg**: Prior period daily average

**Sorting:**
- Default: Date descending (most recent first)
- Click column headers to sort

**Pagination:**
- 30 rows per page
- Navigate with pagination controls

---

## Breakdown Views

### By Cloud

Shows costs grouped by cloud provider (AWS, Azure, GCP).

**Use Cases:**
- Compare spending across providers
- Identify which provider is driving cost changes
- Multi-cloud cost allocation

### By Pool

Shows costs grouped by budget pools.

**Use Cases:**
- Track pool budget utilization
- Identify which teams/projects are overspending
- Chargeback and showback reporting

**Note**: Pools must be set up and resources must be assigned to pools for this view to be meaningful.

### By Owner

Shows costs grouped by resource owner (user).

**Use Cases:**
- Individual cost accountability
- Team cost tracking
- Identify unowned resources

**Note**: Resources must have owner tags or assignments for this view to work effectively.

---

## API Endpoints

### Get Expense Summary
```
GET /api/v1/organizations/{org_id}/expenses/summary
```

**Response:**
```json
{
  "total_cost": 5432.10,
  "daily_average": 181.07,
  "forecast": 5800.00,
  "previous_period_total": 5100.00,
  "change_pct": 6.51,
  "currency": "USD",
  "start_date": "2026-03-10",
  "end_date": "2026-04-09"
}
```

### Get Expense Breakdown
```
GET /api/v1/organizations/{org_id}/expenses/breakdown?group_by=cloud&start_date=2026-03-10&end_date=2026-04-09
```

**Query Parameters:**
- `group_by` (string): `cloud`, `service`, `region`, `pool`, or `owner`
- `start_date` (string): ISO date (YYYY-MM-DD)
- `end_date` (string): ISO date (YYYY-MM-DD)

**Response:**
```json
{
  "breakdown": [
    {"group": "aws", "cost": 3200.00, "pct": 58.9},
    {"group": "azure", "cost": 1500.00, "pct": 27.6},
    {"group": "gcp", "cost": 732.10, "pct": 13.5}
  ],
  "total": 5432.10,
  "currency": "USD"
}
```

### Get Raw Expense Data
```
GET /api/v1/organizations/{org_id}/expenses/clean
```

Returns raw expense line items from MongoDB for custom analysis.

### Get Cache Status
```
GET /api/v1/organizations/{org_id}/expenses/cache-status
```

**Response:**
```json
{
  "cache_status": "fresh",
  "last_updated": "2026-04-09T12:00:00Z",
  "cache_ttl_seconds": 21600
}
```

### Refresh Cache
```
POST /api/v1/organizations/{org_id}/expenses/refresh
```

Manually trigger expense data refresh.

---

## Configuration

### Cache Settings

Configurable in `backend/app/core/config.py`:

```python
# Expense Cache TTLs
COST_CACHE_TTL_HOURS = 6              # 6 hours
COST_CACHE_STALE_HOURS = 24           # 24 hours (max stale data)
COST_CACHE_AUTO_REFRESH = True        # Auto-refresh cache
COST_CACHE_FALLBACK_TO_LIVE = True    # Fallback to live data if cache misses
```

### Date Range Defaults

Default date range is last 30 days. Users can override using the date picker.

---

## Use Cases

### 1. Identify Cost Spikes

**Steps:**
1. Set date range to last 30 days
2. View the trend chart
3. Look for sudden increases
4. Switch to "By Cloud" view to identify provider
5. Navigate to Resources page to find specific resources

### 2. Track Budget Progress

**Steps:**
1. Set date range to current month
2. View "By Pool" breakdown
3. Compare against pool budget limits
4. Identify pools approaching or exceeding budget

### 3. Compare Month-over-Month

**Steps:**
1. Set date range to last 90 days
2. Review period-over-period comparison table
3. Look at change percentages
4. Identify trends (increasing/decreasing)

### 4. Analyze Service-Level Costs

**Steps:**
1. Set desired date range
2. Note: Service breakdown available via API
3. Use Export feature for detailed service analysis
4. Filter by specific services in exported data

---

## Best Practices

1. **Review Weekly**: Check expenses weekly for anomalies
2. **Set Baseline**: Understand your normal daily/monthly spend
3. **Investigate Spikes**: Any spike >20% should be investigated
4. **Track Trends**: Look for consistent upward trends that may need action
5. **Compare Periods**: Use period-over-period to validate optimization efforts
6. **Allocate Costs**: Use pools and tags for accurate cost allocation
7. **Export Regularly**: Create monthly expense reports using Export feature

---

## Troubleshooting

### No Data Displayed

**Possible Causes:**
1. No cloud accounts connected
2. Date range before first account connection date
3. Expense scheduler not run yet
4. Cloud provider API errors

**Solutions:**
1. Verify cloud accounts exist and are healthy
2. Adjust date range to recent dates
3. Check **Schedulers** page for expense collection status
4. View backend logs for errors

### Costs Seem Incorrect

**Validation Steps:**
1. Compare costs with cloud provider consoles
2. Check if all accounts are included
3. Verify date range is correct
4. Look for currency conversion issues

**Note**: Costs should match cloud provider billing dashboards. Small differences may occur due to:
- Timing of data collection
- Currency conversion rates
- Tax inclusion/exclusion

### Cache Appears Stale

**Check Cache Status:**
```
GET /api/v1/organizations/{org_id}/expenses/cache-status
```

**Force Refresh:**
```
POST /api/v1/organizations/{org_id}/expenses/refresh
```

**Check Scheduler:**
- Navigate to **Schedulers** page
- Ensure expense collection scheduler is enabled
- Check last run status and logs

---

## Next Steps

- **[Dashboard](dashboard.md)** - High-level cost overview
- **[Cloud Accounts](cloud-accounts.md)** - Manage connected accounts
- **[Pools](pools.md)** - Set up budget pools for allocation
- **[Data Export](exports.md)** - Create detailed expense reports

---

**Related Documentation:**
- [Overview](overview.md)
- [API Reference](api-reference.md)
- [How to Export Data](guides/export-data.md)
