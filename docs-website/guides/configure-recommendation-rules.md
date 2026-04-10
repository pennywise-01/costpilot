# How to Configure Recommendation Rules

Create custom optimization recommendations based on your infrastructure's specific patterns.

---

## Overview

Recommendation Rules allow you to define custom suggestions for optimizing your cloud resources based on naming patterns, tags, resource types, and other attributes.

**Time Required:** 10-20 minutes  
**Prerequisites:**
- Cloud accounts connected
- Engineer or Organization Admin role
- Understanding of your infrastructure patterns

---

## When to Use Custom Rules

Custom rules are useful when:

- Built-in recommendations don't cover your specific use cases
- You have internal naming/tagging conventions
- You want to enforce organization-specific best practices
- You need to track custom optimization opportunities

---

## Planning Your Rules

### Step 1: Identify Patterns

Think about resources you want to optimize:

**Questions to Ask:**
- Do we have naming conventions? (e.g., `dev-`, `staging-`, `prod-`)
- Do we use tags consistently? (e.g., `environment=production`)
- Are there resource types we want to monitor?
- Are there specific regions we operate in?

**Examples:**
- Development instances that might be idle after hours
- Resources missing security tags
- Single-AZ deployments in production
- Untagged resources

---

### Step 2: Define Savings

For each rule, estimate potential savings:

**Fixed Amount:**
- Use when savings are predictable
- Example: "Terminate idle dev servers: saves $50/month each"

**Percentage:**
- Use when savings vary by resource cost
- Example: "Right-size instances: saves 40% of cost"

---

### Step 3: Draft Conditions

Plan the conditions that identify target resources:

**Example Rule: Idle Development Servers**

Conditions:
```
1. tag_is: environment=development
2. resource_type_is: EC2 Instance
```

This matches all EC2 instances tagged as development.

---

## Creating Your First Rule

### Example: Idle Development Instances

**Step 1: Navigate to Recommendation Rules**
1. Click **"Recommendation Rules"** in left sidebar
2. Click **"Create Rule"**

---

**Step 2: Fill in Basic Information**

- **Name**: `Identify idle development instances`
- **Description**: `Finds EC2 instances tagged as development that may be idle or underutilized. Consider stopping or terminating these instances during non-working hours to save costs.`

---

**Step 3: Set Category and Severity**

- **Category**: `Cost` (this reduces costs)
- **Severity**: `Medium` (important but not critical)

---

**Step 4: Configure Savings**

- **Savings Type**: `Percentage`
- **Savings Value**: `60` (60% savings potential)

This means if a resource costs $100/month, the recommendation will show $60/month potential savings.

---

**Step 5: Add Conditions**

Click **"Add Condition"** twice:

**Condition 1:**
- Type: `tag_is`
- Value: `environment=development`

**Condition 2:**
- Type: `resource_type_is`
- Value: `EC2 Instance`

---

**Step 6: Create Rule**

Click **"Create Rule"** to save.

---

**Step 7: Verify**

1. Navigate to **Recommendations** page
2. Wait for scheduler to run (or trigger manually)
3. Look for recommendations in **Cost** category
4. You should see recommendations matching your rule

---

## Creating Additional Rules

### Rule 1: Unencrypted Production Storage

**Purpose:** Ensure production storage is encrypted

**Configuration:**
- **Name**: `Unencrypted production storage`
- **Description**: `Production storage resources should have encryption enabled for security compliance.`
- **Category**: `Security`
- **Severity**: `Critical`
- **Savings Type**: `Fixed`
- **Savings Value**: `0` (security improvement, not cost savings)

**Conditions:**
```
1. tag_is: environment=production
2. resource_type_is: S3 Bucket
```

---

### Rule 2: Single AZ Production Resources

**Purpose:** Ensure production resources are multi-AZ

**Configuration:**
- **Name**: `Single AZ production resources`
- **Description**: `Production resources should be deployed across multiple availability zones for high availability.`
- **Category**: `Reliability`
- **Severity**: `High`
- **Savings Type**: `Fixed`
- **Savings Value**: `0`

**Conditions:**
```
1. tag_is: environment=production
2. cloud_is: aws
```

---

### Rule 3: Missing Team Tags

**Purpose:** Enforce tagging standards

**Configuration:**
- **Name**: `Resources missing team tags`
- **Description**: `Production and staging resources should have team ownership tags for cost allocation.`
- **Category**: `Operational Excellence`
- **Severity**: `Medium`
- **Savings Type**: `Fixed`
- **Savings Value**: `0`

**Conditions:**
```
1. tag_exists: environment
```

---

### Rule 4: Staging Resources Running 24/7

**Purpose:** Identify staging resources that could be scheduled

**Configuration:**
- **Name**: `Staging running 24/7`
- **Description**: `Staging environments could be shut down during non-working hours to save costs.`
- **Category**: `Cost`
- **Severity**: `Medium`
- **Savings Type**: `Percentage`
- **Savings Value**: `65` (savings from running only 8 hours/day)

**Conditions:**
```
1. tag_is: environment=staging
2. resource_type_is: EC2 Instance
```

---

## Testing Your Rules

### Step 1: Manually Trigger Scheduler

1. Navigate to **Schedulers** page
2. Find the **Recommendation Generation** scheduler
3. Click **"Trigger"**
4. Wait for run to complete

---

### Step 2: Review Recommendations

1. Navigate to **Recommendations** page
2. Filter by category (Cost, Security, etc.)
3. Look for recommendations generated by your rules
4. Click on recommendations to see affected resources

---

### Step 3: Validate Matches

For each recommendation:
1. Check that affected resources are correct
2. Verify savings estimates are realistic
3. Ensure description is helpful

**If Recommendations Are Wrong:**
- Edit the rule conditions
- Make conditions more specific
- Test again

---

## Advanced Rule Patterns

### Pattern 1: Name-Based Matching

**Use Case:** Resources follow naming conventions

**Example:** All resources starting with `prod-web-`

```
Condition: name_starts_with
Value: prod-web-
```

---

### Pattern 2: Multiple Tags

**Use Case:** Match resources with specific tag combinations

**Example:** Production backend resources

```
Condition 1: tag_is
Value: environment=production

Condition 2: tag_is
Value: team=backend
```

Both conditions must match (AND logic).

---

### Pattern 3: Region-Specific Rules

**Use Case:** Different rules for different regions

**Example:** Resources in us-east-1

```
Condition 1: cloud_is
Value: aws

Condition 2: region_is
Value: us-east-1
```

---

### Pattern 4: Broad Catch-All

**Use Case:** Flag all untagged resources

**Example:** Resources without environment tag

```
Note: This requires checking tag does NOT exist
Use: Resources where 'environment' tag is missing
```

Create a rule that matches resources you expect to have tags, then review which don't.

---

## Best Practices

### Rule Design

1. **Be Specific**: Use multiple conditions to avoid false positives
2. **Start Narrow**: Test with narrow conditions, then broaden
3. **Use Tags**: Tags are more reliable than name patterns
4. **Document Well**: Write clear descriptions explaining the "why"
5. **Set Realistic Savings**: Base estimates on actual data

### Rule Organization

1. **Naming Convention**: Use format `[Category] Description`
   - Examples: `Cost: Idle development instances`, `Security: Unencrypted storage`
2. **Consistent Severity**: Align severity with actual business impact
3. **Review Quarterly**: Audit rules for relevance
4. **Disable Unused**: Disable instead of delete if unsure

### Condition Selection

1. **Prefer Tags Over Names**: Tags are more structured
2. **Combine Conditions**: Use 2-3 conditions for precision
3. **Test First**: Manually verify conditions match expected resources
4. **Avoid Overly Broad**: Don't match all AWS resources unless intentional

---

## Troubleshooting

### No Recommendations Generated

**Check:**
1. Rule is active (not disabled)
2. Conditions match existing resources
3. Scheduler has run since rule creation
4. Resources have the expected tags/attributes

**Debug:**
1. Review resources to see if any match conditions
2. Temporarily broaden conditions to test
3. Check backend logs for rule evaluation errors

---

### Too Many Recommendations

**Check:**
1. Conditions too broad
2. Matching more resources than intended

**Solutions:**
1. Add more conditions to narrow matches
2. Make conditions more specific
3. Use exact matches instead of "contains" or "starts_with"

---

### Savings Estimates Incorrect

**Solutions:**
1. Review actual resource costs
2. Adjust savings type (fixed vs percentage)
3. Update savings value based on real data
4. Consider different savings for different resource types

---

### Rule Not Matching Expected Resources

**Debug:**
1. Check resource attributes in **Resources** page
2. Verify tags are exactly as specified (case-sensitive)
3. Ensure resource type matches exactly
4. Test conditions one at a time

**Common Issues:**
- Tag value mismatch: `development` vs `dev`
- Resource type name differences: `EC2 Instance` vs `ec2`
- Region format: `us-east-1` vs `US East (N. Virginia)`

---

## Example Rule Library

Build a library of rules for common scenarios:

| Rule Name | Category | Conditions | Savings |
|-----------|----------|------------|---------|
| Idle dev instances | Cost | `environment=development` + `EC2 Instance` | 60% |
| Unencrypted prod storage | Security | `environment=production` + `S3 Bucket` | $0 |
| Single AZ prod | Reliability | `environment=production` + `aws` | $0 |
| Missing team tags | Op Excellence | `tag_exists: environment` | $0 |
| Staging 24/7 | Cost | `environment=staging` + `EC2 Instance` | 65% |
| Old snapshots | Cost | `name_contains: old-snapshot` | $50 |
| Over-provisioned RDS | Cost | `resource_type_is: RDS Database` + `env=dev` | 40% |
| Public prod resources | Security | `environment=production` + `public=true` | $0 |

---

## Next Steps

- **[Recommendations](../recommendations.md)** - View generated recommendations
- **[Resources](../resources.md)** - See resources matching your rules
- **[Rules Engine](../rules-engine.md)** - Auto-assign resources to pools
- **[Schedulers](../schedulers.md)** - Configure recommendation generation frequency

---

**Need Help?**
- Check [Recommendation Rules Documentation](../recommendation-rules.md)
- Review [Recommendations Documentation](../recommendations.md)
- Check backend logs: `docker-compose logs -f backend`
