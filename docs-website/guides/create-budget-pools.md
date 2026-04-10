# How to Create Budget Pools

Organize your cloud costs using a hierarchical budget pool structure.

---

## Overview

Budget pools allow you to organize costs by team, project, environment, or any structure that makes sense for your organization. Pools can be nested to create a hierarchy, and each pool can have a budget limit.

**Time Required:** 15-30 minutes for initial setup  
**Prerequisites:**
- Cloud accounts connected
- Understanding of your organizational structure
- Organization Admin or Billing Admin role

---

## Planning Your Pool Structure

### Step 1: Decide on Hierarchy

Think about how you want to organize costs:

**Common Approaches:**

**By Team:**
```
Root Pool
├── Backend Team
├── Frontend Team
├── Data Science
└── DevOps
```

**By Environment:**
```
Root Pool
├── Production
├── Staging
├── Development
└── Testing
```

**By Project:**
```
Root Pool
├── Project Alpha
├── Project Beta
└── Project Gamma
```

**Hybrid (Recommended):**
```
Root Pool
├── Engineering
│   ├── Backend Team
│   │   ├── Production APIs
│   │   └── Development
│   └── Frontend Team
│       ├── Production CDN
│       └── Staging
├── Data Science
│   └── ML Training
└── Infrastructure
    ├── Production
    └── CI/CD
```

---

### Step 2: Set Budgets

For each pool, decide if you want to set a budget limit:

**Questions to Ask:**
- What is the monthly budget for this team/project?
- Do we need to track vs. a specific limit?
- Is this pool just for tracking (no limit)?

**Example Budgets:**
- Backend Team: $8,000/month
- ML Training: $15,000/month (expensive GPU instances)
- CI/CD: $2,000/month

---

## Creating Pools

### Step 1: Create Root-Level Pools

1. Navigate to **Pools** page
2. Click **"Create Pool"**

**Example: Engineering Pool**

- **Name**: `Engineering`
- **Budget Limit**: `20000` ($20,000)
- **Purpose**: `Business Unit`
- **Parent Pool**: Leave blank (root-level)

3. Click **"Create"**

---

### Step 2: Create Child Pools

1. Find the **Engineering** pool in the tree
2. Click **"Create Sub-pool"** (or expand and click create under it)

**Example: Backend Team Pool**

- **Name**: `Backend Team`
- **Budget Limit**: `8000` ($8,000)
- **Purpose**: `Team`
- **Parent Pool**: `Engineering` (auto-selected if using sub-pool)

3. Click **"Create"**

---

### Step 3: Create Deeper Nesting

Repeat for deeper levels:

**Example: Production APIs Pool**

- **Name**: `Production APIs`
- **Budget Limit**: `5000` ($5,000)
- **Purpose**: `Project`
- **Parent Pool**: `Backend Team`

---

### Step 4: Create Parallel Pools

Create other root-level pools:

**Data Science Pool:**
- **Name**: `Data Science`
- **Budget Limit**: `20000`
- **Purpose**: `Business Unit`
- **Parent Pool**: None (root-level)

**ML Training Pool (child of Data Science):**
- **Name**: `ML Training`
- **Budget Limit**: `15000`
- **Purpose**: `ML/AI`
- **Parent Pool**: `Data Science`

---

## Assigning Resources to Pools

### Option 1: Manual Assignment

1. Navigate to **Resources** page
2. Click on a resource
3. Click **"Edit"**
4. Select **Pool** from dropdown
5. Click **"Save"**

**Best For:** Few resources, manual control

---

### Option 2: Rules Engine (Recommended)

Automate resource assignment using rules:

1. Navigate to **Rules Engine** (or use API)
2. Create rules that match resources and assign to pools

**Example Rule:**
```
Name: Production EC2 to Engineering pool
Priority: 10
Pool: Engineering > Backend Team
Conditions:
  - tag_is: environment=production
  - resource_type_is: EC2 Instance
```

**Best For:** Many resources, automated management

---

### Option 3: Tag-Based Assignment

Ensure resources have tags that match your rules:

**Recommended Tags:**
- `team`: backend, frontend, data-science, devops
- `environment`: production, staging, development
- `project`: project name

**Then create rules:**
```
If tag "team=backend" → Assign to Backend Team pool
If tag "environment=production" → Assign to Production pool
```

---

## Monitoring Pool Budgets

### Step 1: View Pool Utilization

1. Navigate to **Pools** page
2. Review utilization bars:
   - **Green**: <75% (under budget)
   - **Yellow**: 75-90% (approaching budget)
   - **Orange**: 90-100% (near budget)
   - **Red**: >100% (over budget)

---

### Step 2: Drill Down into Pools

1. Click on a pool to expand it
2. See child pools and their utilization
3. Understand where costs are coming from

---

### Step 3: View Costs by Pool

1. Navigate to **Expenses** page
2. Switch view to **"By Pool"**
3. See cost breakdown by pool
4. Compare pools side-by-side

---

## Managing Pools

### Editing a Pool

1. Click on pool name
2. Click **"Edit"**
3. Modify:
   - Name
   - Budget limit
   - Purpose
   - Parent pool (changes hierarchy)
4. Click **"Save"**

---

### Deleting a Pool

1. Click on pool name
2. Click **"Delete"**
3. Confirm deletion

**Important:**
- Must delete child pools first
- Resources assigned to deleted pool become unassigned
- Historical cost data is preserved

---

### Reassigning Pool Ownership

1. Click on pool name
2. Click **"Edit"**
3. Change owner (if applicable)
4. Click **"Save"**

---

## Best Practices

### Pool Design

1. **Keep It Simple**: Max 3-4 levels deep
2. **Align with Org**: Mirror your organizational structure
3. **Use Purposes**: Consistently apply purpose types
4. **Name Clearly**: Avoid ambiguous names
5. **Document Structure**: Share pool hierarchy with team

### Budget Management

1. **Set Realistic Budgets**: Base on historical data
2. **Review Monthly**: Check utilization monthly
3. **Adjust as Needed**: Update budgets when requirements change
4. **Alert on Thresholds**: Set up notifications at 75%, 90%, 100%
5. **Chargeback**: Use pool data for internal billing

### Resource Assignment

1. **Automate with Rules**: Don't assign manually at scale
2. **Tag Consistently**: Enforce tagging standards
3. **Audit Regularly**: Verify resources are in correct pools
4. **Handle Untagged**: Create "Untagged Resources" pool as catch-all

---

## Example Pool Structures

### Startup (< 50 people)

```
Root Pool
├── Product Engineering (Budget: $15,000)
│   ├── Production (Budget: $10,000)
│   └── Development (Budget: $5,000)
├── Data & ML (Budget: $10,000)
│   └── Model Training (Budget: $8,000)
└── Infrastructure (Budget: $3,000)
    └── CI/CD (Budget: $2,000)
```

---

### Mid-Size Company (50-200 people)

```
Root Pool
├── Engineering (Budget: $50,000)
│   ├── Backend (Budget: $20,000)
│   │   ├── Production APIs (Budget: $12,000)
│   │   └── Staging (Budget: $8,000)
│   ├── Frontend (Budget: $10,000)
│   │   ├── Production CDN (Budget: $5,000)
│   │   └── Build Servers (Budget: $5,000)
│   └── DevOps (Budget: $20,000)
│       ├── Production Infra (Budget: $15,000)
│       └── CI/CD (Budget: $5,000)
├── Data Science (Budget: $30,000)
│   ├── Training (Budget: $20,000)
│   └── Inference (Budget: $10,000)
├── Marketing (Budget: $5,000)
│   └── Analytics (Budget: $5,000)
└── Corporate IT (Budget: $10,000)
    └── Internal Tools (Budget: $10,000)
```

---

## Troubleshooting

### Pool Shows Unexpected Costs

**Check:**
1. Resources assigned to pool are correct
2. Child pools are contributing to parent's total
3. Rules Engine rules are assigning correctly
4. Expense data is fresh

**Solutions:**
1. Review resources in pool
2. Check child pools
3. Verify rule assignments
4. Reassign resources if needed

---

### Budget Not Tracking Correctly

**Check:**
1. Budget limit is set (not blank)
2. Resources are assigned to correct pool
3. Pools are in correct hierarchy
4. Date range is current month

---

### Can't Delete Pool

**Possible Causes:**
1. Pool has child pools
2. Resources still assigned to pool

**Solutions:**
1. Delete or reassign child pools first
2. Reassign resources to different pool
3. Then delete the pool

---

### Resources Not Appearing in Pool

**Check:**
1. Resource is assigned to pool
2. Resource has cost data
3. Date range includes resource costs
4. Filters aren't excluding the resource

---

## Next Steps

After setting up pools:

- **[Rules Engine](../rules-engine.md)** - Automate resource assignment
- **[Expenses](../expenses.md)** - View costs by pool
- **[Notifications](../notifications.md)** - Set up budget alerts
- **[Users](../users.md)** - Assign pool owners

---

**Need Help?**
- Check [Pools Documentation](../pools.md)
- Review [Rules Engine Documentation](../rules-engine.md)
- Check backend logs: `docker-compose logs -f backend`
