# Budget Pools

![Pools Page](screenshots/pools-page.png)

Organize and track cloud costs using a hierarchical budget pool structure.

---

## Overview

Budget Pools provide a hierarchical organization of cloud costs aligned with your organizational structure, projects, or teams. Each pool can have a budget limit and tracks actual spending with utilization progress.

**URL**: `/pools`

**Key Features:**
- Hierarchical pool structure (parent-child relationships)
- Budget limits with utilization tracking
- Purpose-based categorization
- Real-time spent vs. budget tracking
- Progress bars for visual status
- Pool-based cost allocation

**As shown in the screenshot above:**
- Default "Test Organization" pool created automatically
- Pool information displayed including budget and spend
- "Create Pool" button for adding new pools
- Pool hierarchy tree view (expandable for nested pools)

---

## Page Layout

### Pool Tree View

The pools are displayed in a tree structure showing parent-child relationships:

**Each Pool Card Shows:**
- **Pool Name**: Descriptive name (clickable to expand/edit)
- **Purpose Badge**: Budget, Business Unit, Team, Project, CI/CD, ML/AI, or Asset Pool
- **Budget Limit**: Set budget amount (if configured)
- **Spent**: Current month's spend in this pool (includes child pools)
- **Utilization Bar**: Visual progress bar showing spent vs. budget
  - Green: <75% utilized
  - Yellow: 75-90% utilized
  - Orange: 90-100% utilized
  - Red: >100% (over budget)
- **Percentage**: Numeric utilization percentage
- **Actions**: Edit, Delete, Create Sub-pool

**Tree Indicators:**
- **▼**: Pool is expanded, showing child pools
- **▶**: Pool is collapsed, click to expand
- **Indentation**: Shows hierarchy depth

---

## Purpose Types

Each pool has a purpose to indicate its role:

| Purpose | Use Case | Example |
|---------|----------|---------|
| **Budget** | General budget tracking | "Q1 2026 Budget" |
| **Business Unit** | Organizational division | "Engineering", "Marketing" |
| **Team** | Specific team | "Backend Team", "Data Science" |
| **Project** | Time-bound initiative | "Mobile App Rewrite" |
| **CI/CD** | Build and deployment | "GitHub Actions", "Jenkins" |
| **ML/AI** | Machine learning workloads | "Model Training", "Inference" |
| **Asset Pool** | Shared infrastructure | "Production Servers", "Databases" |

---

## Creating a Pool

### Step 1: Click Create

- Navigate to **Pools** page
- Click **"Create Pool"** button (or **"Create Sub-pool"** for nested pool)

---

### Step 2: Fill in Pool Details

**Pool Name:**
- Clear, descriptive name
- Examples: "Backend Team", "Production Infrastructure", "ML Training"
- Max 255 characters

**Budget Limit (Optional):**
- Monthly budget for this pool
- Enter amount in USD
- Leave blank for unlimited budget (tracking only)
- Examples: 1000, 5000, 10000

**Purpose:**
- Select from dropdown:
  - Budget
  - Business Unit
  - Team
  - Project
  - CI/CD
  - ML/AI
  - Asset Pool

**Parent Pool (Optional):**
- Select a parent pool to create a nested structure
- Leave blank for top-level pool
- Child pools contribute to parent's total spent

**Example:**
```
Name: Backend Team
Budget Limit: 5000
Purpose: Team
Parent Pool: Engineering
```

---

### Step 3: Save

- Click **"Create"**
- Pool appears in the tree view
- Resources can now be assigned to this pool

---

## Pool Hierarchy Example

```
Root Pool (Organization)
├── Engineering (Business Unit) - Budget: $20,000
│   ├── Backend Team (Team) - Budget: $8,000
│   │   ├── API Servers (Project) - Budget: $5,000
│   │   └── Workers (Project) - Budget: $3,000
│   ├── Frontend Team (Team) - Budget: $4,000
│   └── Infrastructure (Team) - Budget: $8,000
│       ├── Production (Asset Pool) - Budget: $6,000
│       └── Staging (Asset Pool) - Budget: $2,000
├── Data Science (Business Unit) - Budget: $15,000
│   ├── Model Training (ML/AI) - Budget: $10,000
│   └── Inference (ML/AI) - Budget: $5,000
└── CI/CD (CI/CD) - Budget: $2,000
    └── GitHub Actions (Asset Pool) - Budget: $2,000
```

**How Costs Roll Up:**
- API Servers spends $4,500 → rolls up to Backend Team
- Backend Team total (API Servers + Workers) = $7,200 → rolls up to Engineering
- Engineering total (Backend + Frontend + Infrastructure) = $18,500
- Root Pool shows organization-wide total

---

## Editing a Pool

1. Click on the pool name in the tree
2. Click **"Edit"**
3. Modify any field (name, budget, purpose, parent)
4. Click **"Save"**

**Note**: Changing parent pool affects hierarchy and cost rollup.

---

## Deleting a Pool

1. Click on the pool name
2. Click **"Delete"**
3. Confirm deletion

**Important:**
- Deleting a pool with child pools will fail (delete children first)
- Resources assigned to deleted pool become unassigned
- Historical cost data is preserved

---

## Pool Policies

Pools can have policies that govern behavior:

**View Policies:**
```
GET /api/v1/pools/{id}/policies
```

**Create Policy:**
```
POST /api/v1/pools/{id}/policies
```

**Policy Types:**
- Budget threshold alerts
- Auto-assignment rules
- Cost allocation rules

---

## API Endpoints

### Create Pool
```
POST /api/v1/organizations/{org_id}/pools
```

**Request Body:**
```json
{
  "name": "Backend Team",
  "budget_limit": 8000.00,
  "purpose": "team",
  "parent_id": "engineering-pool-id"
}
```

### List Pools
```
GET /api/v1/organizations/{org_id}/pools
```

**Response:**
```json
{
  "pools": [
    {
      "id": "pool-uuid",
      "name": "Backend Team",
      "purpose": "team",
      "budget_limit": 8000.00,
      "spent": 7200.00,
      "utilization_pct": 90.0,
      "parent_id": "engineering-pool-id",
      "parent_name": "Engineering",
      "children": [],
      "created_at": "2026-04-01T10:00:00Z"
    }
  ],
  "tree": [
    {
      "id": "root-pool-id",
      "name": "Root Pool",
      "children": [
        {
          "id": "engineering-pool-id",
          "name": "Engineering",
          "budget_limit": 20000.00,
          "spent": 18500.00,
          "utilization_pct": 92.5,
          "children": [
            {
              "id": "backend-team-id",
              "name": "Backend Team",
              "budget_limit": 8000.00,
              "spent": 7200.00,
              "utilization_pct": 90.0,
              "children": []
            }
          ]
        }
      ]
    }
  ]
}
```

### Get Single Pool
```
GET /api/v1/pools/{id}
```

### Update Pool
```
PATCH /api/v1/pools/{id}
```

### Delete Pool
```
DELETE /api/v1/pools/{id}
```

---

## Use Cases

### 1. Team-Based Cost Tracking

**Setup:**
```
Root Pool
├── Backend Team (Budget: $8,000)
├── Frontend Team (Budget: $4,000)
└── DevOps Team (Budget: $6,000)
```

**Benefit:** Each team's cloud costs are tracked separately for chargeback.

---

### 2. Project-Based Budgeting

**Setup:**
```
Root Pool
├── Project Alpha (Budget: $10,000)
├── Project Beta (Budget: $15,000)
└── Project Gamma (Budget: $5,000)
```

**Benefit:** Track spending per project and ensure budgets aren't exceeded.

---

### 3. Environment Separation

**Setup:**
```
Root Pool
├── Production (Budget: $20,000)
│   ├── Web Servers (Budget: $12,000)
│   └── Databases (Budget: $8,000)
├── Staging (Budget: $5,000)
└── Development (Budget: $3,000)
```

**Benefit:** Monitor environment-specific costs and optimize accordingly.

---

### 4. ML/AI Cost Isolation

**Setup:**
```
Root Pool
├── Engineering (Budget: $15,000)
└── Data Science (Budget: $20,000)
    └── Model Training (ML/AI, Budget: $15,000)
```

**Benefit:** Isolate expensive ML training costs from regular engineering spend.

---

## Best Practices

### Pool Design

1. **Align with Org Structure**: Mirror your organizational hierarchy
2. **Keep It Simple**: Avoid excessive nesting (max 3-4 levels)
3. **Set Realistic Budgets**: Base budgets on historical data
4. **Use Purpose Types**: Consistently apply purpose categories
5. **Name Clearly**: Use descriptive, unambiguous names

### Budget Management

1. **Review Monthly**: Check pool utilization monthly
2. **Adjust Budgets**: Update budgets as needs change
3. **Monitor Trends**: Watch for consistent over-budget pools
4. **Alert Thresholds**: Set up notifications at 75%, 90%, 100%
5. **Chargeback Reports**: Use pool data for internal billing

### Resource Assignment

1. **Use Rules Engine**: Automate resource-to-pool assignment
2. **Tag Consistently**: Ensure resources have tags for rule matching
3. **Audit Assignments**: Regularly verify resources are in correct pools
4. **Handle Untagged**: Create default pools for untagged resources

---

## Troubleshooting

### Pool Shows Unexpected Costs

**Possible Causes:**
1. Resources incorrectly assigned to pool
2. Child pool costs rolling up
3. Rules Engine misconfiguration

**Solutions:**
1. Review resources assigned to pool
2. Check child pools and their resources
3. Verify Rules Engine rules are correct
4. Reassign resources if needed

### Budget Not Tracking Correctly

**Check:**
1. Budget limit is set (not blank)
2. Resources are assigned to pool (not parent)
3. Expense data is fresh
4. Child pools are contributing to parent

### Can't Delete Pool

**Possible Causes:**
1. Pool has child pools
2. Pool has resources assigned

**Solutions:**
1. Delete or reassign child pools first
2. Reassign resources to different pool
3. Then delete the pool

---

## Next Steps

- **[Rules Engine](rules-engine.md)** - Auto-assign resources to pools
- **[Users](users.md)** - Assign pool owners
- **[Expenses](expenses.md)** - View costs by pool
- **[Notifications](notifications.md)** - Set up budget alerts

---

**Related Documentation:**
- [How to Create Budget Pools](guides/create-budget-pools.md)
- [API Reference](api-reference.md)
