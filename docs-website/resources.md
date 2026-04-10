# Resource Discovery

![Resources Page](screenshots/resources-page.png)

Discover, track, and analyze all cloud resources across your accounts.

---

## Overview

Resource Discovery automatically inventories all your cloud resources (EC2 instances, RDS databases, Lambda functions, S3 buckets, Azure VMs, GCP Compute instances, etc.) and associates costs with each resource.

**URL**: `/resources`

**Key Features:**
- Automatic resource discovery across AWS, Azure, GCP
- Cost attribution per resource
- Advanced filtering (cloud type, region, pool, owner)
- Search by resource name or ID
- Tag visibility and analysis
- Resource detail pages with full metadata

---

## Page Layout

### Filters Bar

At the top of the page, filter resources by:

**Cloud Type:**
- All
- AWS
- Azure
- GCP

**Region:**
- All regions
- Specific regions (e.g., us-east-1, westeurope, us-central1)

**Pool:**
- All pools
- Specific budget pool (for cost allocation)

**Owner:**
- All owners
- Specific user/owner

**Search:**
- Free-text search by resource name or ID

**Apply Filters:**
- Filters are applied in real-time
- Click **"Reset"** to clear all filters

---

### Resources Table

The main table displays discovered resources:

**Columns:**
- **Resource Name**: Name or identifier (clickable to view details)
- **Cloud Provider**: AWS, Azure, or GCP icon
- **Resource Type**: EC2 Instance, RDS Database, VM, etc.
- **Region**: Cloud region where resource is deployed
- **Owner**: Assigned owner (if available)
- **Pool**: Associated budget pool (if available)
- **Daily Cost**: Cost per day for this resource
- **Tags**: Resource tags (key=value pairs)
- **Status**: Running, Stopped, Deleted, etc.

**Sorting:**
- Click column headers to sort
- Default sort: Daily Cost descending (most expensive first)

**Pagination:**
- 50 resources per page
- Navigate with pagination controls

---

## Resource Detail Page

![Resource Detail](screenshots/resources-page.png)

Click on any resource to view detailed information:

**Resource Details:**
- **Resource ID**: Unique identifier
- **Name**: Resource name
- **Cloud Provider**: AWS, Azure, or GCP
- **Resource Type**: Specific service type
- **Region**: Deployment region
- **Status**: Current state
- **Daily Cost**: Cost attribution
- **Monthly Cost**: Projected monthly cost
- **Owner**: Assigned owner
- **Pool**: Budget pool assignment
- **Tags**: All resource tags
- **Created At**: Resource creation timestamp
- **Last Updated**: Last metadata refresh

**Cost History:**
- 30-day cost trend chart
- Daily cost breakdown
- Average daily cost

**Actions:**
- **Edit**: Update owner, pool, or metadata
- **View in Cloud Console**: Link to provider's console (if available)

---

## Supported Resource Types

### AWS Resources
- **EC2 Instances**: Virtual servers
- **RDS Databases**: Managed databases
- **Lambda Functions**: Serverless functions
- **S3 Buckets**: Object storage
- **EBS Volumes**: Block storage
- **Elastic Load Balancers**: Traffic distribution
- **ElastiCache Clusters**: In-memory caches
- **And more**: Any resource with cost attribution

### Azure Resources
- **Virtual Machines**: Compute instances
- **App Services**: Web applications
- **SQL Databases**: Managed databases
- **Storage Accounts**: Blob/file storage
- **Azure Functions**: Serverless functions
- **And more**: Any resource with cost attribution

### GCP Resources
- **Compute Engine Instances**: VMs
- **Cloud SQL**: Managed databases
- **Cloud Functions**: Serverless functions
- **Cloud Storage Buckets**: Object storage
- **And more**: Any resource with cost attribution

---

## API Endpoints

### List Resources
```
GET /api/v1/organizations/{org_id}/resources?limit=50&offset=0&cloud_type=&region=&pool_id=&owner_id=
```

**Query Parameters:**
- `limit` (int): Number of resources to return (default: 50, max: 100)
- `offset` (int): Pagination offset (default: 0)
- `cloud_type` (string): Filter by cloud type (`aws`, `azure`, `gcp`)
- `region` (string): Filter by region
- `pool_id` (string): Filter by budget pool ID
- `owner_id` (string): Filter by owner user ID

**Response:**
```json
{
  "resources": [
    {
      "id": "i-0abc123def456",
      "name": "production-web-server",
      "cloud_type": "aws",
      "resource_type": "EC2 Instance",
      "region": "us-east-1",
      "owner_id": "user-uuid",
      "owner_name": "John Doe",
      "pool_id": "pool-uuid",
      "pool_name": "Production",
      "daily_cost": 12.50,
      "monthly_cost": 375.00,
      "tags": {
        "environment": "production",
        "team": "backend"
      },
      "status": "running",
      "last_updated": "2026-04-09T12:00:00Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

### Get Resource Detail
```
GET /api/v1/resources/{resource_id}
```

**Response:**
```json
{
  "id": "i-0abc123def456",
  "name": "production-web-server",
  "cloud_type": "aws",
  "resource_type": "EC2 Instance",
  "region": "us-east-1",
  "status": "running",
  "daily_cost": 12.50,
  "monthly_cost": 375.00,
  "cost_history": [
    {"date": "2026-04-01", "cost": 12.00},
    {"date": "2026-04-02", "cost": 12.50}
  ],
  "tags": {
    "environment": "production",
    "team": "backend"
  },
  "metadata": {
    "instance_type": "t3.large",
    "vcpus": 2,
    "memory_gb": 8,
    "launch_time": "2026-01-15T10:00:00Z"
  },
  "owner": {
    "id": "user-uuid",
    "name": "John Doe",
    "email": "john@example.com"
  },
  "pool": {
    "id": "pool-uuid",
    "name": "Production"
  }
}
```

---

## Use Cases

### 1. Identify Idle Resources

**Steps:**
1. Navigate to Resources page
2. Filter by cloud type if needed
3. Sort by Daily Cost (ascending)
4. Look for resources with very low or zero cost
5. Click to view details and verify status
6. Consider terminating or downsizing idle resources

### 2. Find Untagged Resources

**Steps:**
1. View resources list
2. Look for resources with empty or minimal tags
3. Tagging is essential for cost allocation
4. Work with resource owners to add tags
5. Use Rules Engine to auto-assign untagged resources

### 3. Track Resource Ownership

**Steps:**
1. Filter by Owner to see individual user's resources
2. Verify ownership is correctly assigned
3. Use tags or Rules Engine to assign ownership
4. Ensure all resources have an owner for accountability

### 4. Analyze Regional Distribution

**Steps:**
1. Filter by Region
2. Understand geographic distribution of resources
3. Identify opportunities for regional consolidation
4. Consider data transfer costs between regions

### 5. Monitor Resource Costs Over Time

**Steps:**
1. Click on a resource to view details
2. Review cost history chart
3. Identify cost changes or anomalies
4. Correlate with infrastructure changes

---

## Resource Tagging Strategy

Effective tagging is critical for cost allocation and resource management.

### Recommended Tags

**Business Tags:**
- `environment`: production, staging, development, test
- `team`: backend, frontend, data-science, devops
- `project`: project name or ID
- `owner`: individual or team responsible
- `cost-center`: billing code or department

**Technical Tags:**
- `service`: application or service name
- `version`: deployment version
- `managed-by`: terraform, pulumi, manual, etc.

### Tag Best Practices

1. **Define Standards**: Establish tagging conventions organization-wide
2. **Automate**: Use infrastructure-as-code to enforce tags
3. **Require Critical Tags**: Make certain tags mandatory
4. **Audit Regularly**: Review tagging compliance
5. **Use Rules Engine**: Auto-assign tags based on naming patterns

---

## Configuration

### Cache Settings

```python
# Resource Cache TTL (seconds)
CACHE_TTL_RESOURCES = 300  # 5 minutes
CLOUD_CACHE_TTL_SECONDS = 300  # 5 minutes
```

### Resource Discovery Timeout

```python
# Cloud account live data timeout (seconds)
CLOUD_ACCOUNT_LIVE_DATA_TIMEOUT = 60  # 60 seconds
```

---

## Troubleshooting

### Resources Not Appearing

**Possible Causes:**
1. Cloud accounts recently connected (discovery in progress)
2. Resource scheduler not running
3. Cloud provider API errors
4. Filters too restrictive

**Solutions:**
1. Wait a few minutes for initial discovery
2. Check **Schedulers** page for resource collection status
3. Clear filters and try again
4. Verify resources exist in cloud provider console
5. Check backend logs for errors

### Costs Not Attributed to Resources

**Possible Causes:**
1. Cost data not yet collected
2. Shared or unattributable costs
3. Cloud provider doesn't support per-resource costs for that service

**Solutions:**
1. Wait for next scheduler run
2. Check cloud provider cost allocation settings
3. Enable detailed billing reports in cloud console

### Stale Resource Data

**Force Refresh:**
- Resource data refreshes automatically every 5 minutes
- Manual refresh not currently available in UI
- Check scheduler status to ensure it's running

---

## Next Steps

- **[Rules Engine](rules-engine.md)** - Auto-assign resources to pools
- **[Pools](pools.md)** - Organize resources into budget pools
- **[Recommendations](recommendations.md)** - Find optimization opportunities
- **[Data Export](exports.md)** - Export resource inventory

---

**Related Documentation:**
- [Cloud Accounts](cloud-accounts.md)
- [Expense Tracking](expenses.md)
- [API Reference](api-reference.md)
