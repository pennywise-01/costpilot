# Dashboard Documentation

![CostPilot Dashboard](screenshots/dashboard.png)

The Dashboard is your central command center for cloud cost visibility and insights.

---

## Overview

The Dashboard provides a comprehensive view of your cloud spending across all connected accounts (AWS, Azure, GCP). It displays key metrics, trends, and actionable insights to help you understand and optimize costs.

**URL**: `/`

---

## Key Metrics

### Top Row Cards

As shown in the screenshot above, the dashboard displays:

1. **Monthly Cost** (`$0/mo`)
   - Current month's total cloud spend
   - Includes all connected cloud accounts
   - Updated in real-time with 5-minute cache
   - Shows $0 when no cloud accounts are connected yet

2. **Cloud Providers**
   - Icons for connected providers (AWS, Azure, GCP)
   - Visual indicator of integration status

3. **Trend Indicators**
   - Week-over-week and month-over-month changes
   - Percentage change indicators (up/down arrows)

4. **Cost Trend Chart**
   - 30-day line chart showing cost over time
   - Currently shows flat line ($0) as no accounts connected
   - Will populate once cloud accounts are added

**Features:**
- **Time Range**: Last 30 days
- **Chart Type**: Area chart with gradient fill
- **Tooltip**: Hover to see exact daily cost
- **Multi-Cloud**: Shows combined cost from all providers
- **Trend Line**: Visual indicator of spending trajectory

**Use Cases:**
- Identify spending spikes and anomalies
- Track cost trends over time
- Correlate costs with deployments or infrastructure changes
- Validate cost optimization efforts

---

## Cloud Account Cards

Each connected cloud account is displayed as a card with:

- **Account Name**: Provider and account identifier
- **Current Cost**: This month's spend for the account
- **Trend vs Last Month**: Percentage change (↑ or ↓) compared to previous month
- **Mini Chart**: 30-day cost sparkline
- **Status**: Indicator showing if account is actively collecting data

**Interactions:**
- Click on an account card to navigate to **Cloud Account Details** page
- See live cost and resource data for the specific account
- View account-specific recommendations

---

## Top 5 Most Expensive Resources

A ranked list of your highest-cost cloud resources:

**Columns:**
- **Resource Name**: Identifier or name of the resource
- **Cloud Provider**: AWS, Azure, or GCP icon
- **Resource Type**: EC2, RDS, VM, etc.
- **Daily Cost**: Cost per day
- **Region**: Cloud region where resource is deployed

**Use Cases:**
- Quickly identify cost drivers
- Focus optimization efforts on top spenders
- Understand resource distribution

**Note**: Clicking on a resource navigates to the **Resource Detail** page.

---

## Recommendation Savings by Category

Breakdown of potential savings organized by recommendation category:

**Categories:**
- **Cost**: Direct cost reduction opportunities
- **Security**: Security improvements that may reduce risk-related costs
- **Reliability**: Reliability improvements to avoid downtime costs
- **Performance**: Performance optimizations
- **Operational Excellence**: Operational efficiency improvements

**Visualization:**
- Bar chart showing savings amount per category
- Click on a category to see detailed recommendations
- Filter recommendations by cloud provider

---

## Data Freshness & Caching

### Cache TTLs

| Data Type | TTL | Description |
|-----------|-----|-------------|
| Live Cloud Data | 5 minutes | Cost and resource data from cloud APIs |
| Expense Summary | 6 hours | Aggregated expense data |
| Resources | 5 minutes | Resource discovery data |
| Recommendations | 10 minutes | Optimization recommendations |

### Graceful Degradation

- If cloud provider APIs are unavailable, CostPilot falls back to stale cache
- Dashboard shows cached data with a "stale" indicator
- Prevents dashboard from showing errors during temporary outages

### Manual Refresh

To force a cache refresh:
1. Navigate to the specific cloud account details page
2. Click **"Refresh"** button
3. This bypasses cache and fetches live data from the provider

---

## API Endpoints

The dashboard uses the following backend APIs:

```
GET /api/v1/organizations/{org_id}/expenses/summary
GET /api/v1/organizations/{org_id}/expenses/breakdown
GET /api/v1/organizations/{org_id}/expenses/cache-status
POST /api/v1/organizations/{org_id}/expenses/refresh
GET /api/v1/organizations/{org_id}/resources
GET /api/v1/organizations/{org_id}/recommendations
GET /api/v1/cloud-accounts/{id}/live-data
```

---

## Configuration

Cache TTLs can be configured in `backend/app/core/config.py`:

```python
# Cache TTLs (seconds)
CLOUD_CACHE_TTL_SECONDS = 300          # 5 minutes
CACHE_TTL_EXPENSE_SUMMARY = 21600      # 6 hours
CACHE_TTL_RECOMMENDATIONS = 600        # 10 minutes
CACHE_TTL_RESOURCES = 300              # 5 minutes
```

---

## Troubleshooting

### Dashboard Shows Zero Costs

**Possible Causes:**
1. No cloud accounts connected
2. Cloud accounts recently added (data collection in progress)
3. Cloud provider API errors
4. Scheduler not running

**Solutions:**
1. Navigate to **Cloud Accounts** and verify accounts are connected
2. Check **Schedulers** page to ensure expense collection is scheduled
3. View cloud account details to see if live data fetch is successful
4. Check backend logs for errors: `docker-compose logs -f backend`

### Data Appears Stale

**Check Cache Status:**
```
GET /api/v1/organizations/{org_id}/expenses/cache-status
```

**Force Refresh:**
- Navigate to individual cloud account details
- Click **"Refresh"** to fetch live data

### Missing Recommendations

**Ensure:**
- Cloud accounts are connected and healthy
- Recommendation schedulers are running
- Clear recommendation cache: `POST /api/v1/organizations/{org_id}/recommendations/clear-cache`

---

## Best Practices

1. **Review Daily**: Check dashboard daily for cost trends and anomalies
2. **Focus on Top Spenders**: Prioritize optimization efforts on top 5 resources
3. **Monitor Forecast**: Compare forecast against budget to avoid surprises
4. **Act on Recommendations**: Review and implement high-savings recommendations
5. **Set Up Alerts**: Configure notifications for budget thresholds

---

## Next Steps

- **[Cloud Accounts](cloud-accounts.md)** - Connect more cloud providers
- **[Expense Tracking](expenses.md)** - Deep dive into cost analysis
- **[Recommendations](recommendations.md)** - View and act on optimization suggestions
- **[Schedulers](schedulers.md)** - Ensure automated data collection

---

**Related Documentation:**
- [Quick Start Guide](quickstart.md)
- [Overview](overview.md)
- [API Reference](api-reference.md)
