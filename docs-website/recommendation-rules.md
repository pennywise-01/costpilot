# Recommendation Rules

![Recommendation Rules](screenshots/recommendation-rules.png)

Create custom rules that generate recommendations based on resource attributes.

---

## Overview

Recommendation Rules allow you to define custom optimization suggestions based on specific resource characteristics like name patterns, tags, resource types, and cloud providers.

**URL**: `/recommendation-rules`

**Key Features:**
- Custom rule creation with flexible conditions
- Multiple condition types (name, tags, resource type, cloud, region)
- Category and severity assignment
- Savings estimation (fixed or percentage)
- Reusable rule templates
- Enable/disable toggle

---

## Page Layout

### Rules List

The main page displays all your custom rules:

**Columns:**
- **Rule Name**: Descriptive name (clickable to edit)
- **Description**: Brief explanation of the rule
- **Category**: Cost, Security, Reliability, Performance, or Operational Excellence
- **Severity**: Critical, High, Medium, or Low
- **Savings Type**: Fixed amount ($) or Percentage (%)
- **Savings Value**: Estimated savings per recommendation
- **Conditions**: Number of conditions in the rule
- **Status**: Active or Inactive
- **Created By**: User who created the rule
- **Actions**: Edit, Enable/Disable, Delete

**Sorting:**
- Default: Created date descending (newest first)
- Click column headers to sort

**Pagination:**
- 20 rules per page
- Navigate with pagination controls

---

### Create Rule Button

Click **"Create Rule"** to define a new recommendation rule.

---

## Creating a Rule

### Step 1: Basic Information

**Rule Name:**
- Clear, descriptive name
- Example: "Identify idle development servers"
- Max 255 characters

**Description:**
- Detailed explanation of what the rule does
- When it should be applied
- Any caveats or considerations
- Example: "Finds EC2 instances tagged as development with low CPU utilization"

---

### Step 2: Category & Severity

**Category:**
Choose the recommendation category:

- **Cost**: Direct cost reduction opportunities
- **Security**: Security improvements
- **Reliability**: Reliability enhancements
- **Performance**: Performance optimizations
- **Operational Excellence**: Operational efficiency improvements

**Severity:**
Set the priority level:

- **Critical**: Must address immediately (e.g., security vulnerabilities)
- **High**: Should address soon (e.g., significant cost savings)
- **Medium**: Worth considering (e.g., moderate optimizations)
- **Low**: Nice to have (e.g., minor improvements)

---

### Step 3: Savings Configuration

**Savings Type:**
Choose how to estimate savings:

- **Fixed**: Specific dollar amount per recommendation
  - Example: $50/month per resource
  - Use when savings are predictable

- **Percentage**: Percentage of current cost
  - Example: 30% of resource cost
  - Use when savings vary by resource cost

**Savings Value:**
Enter the savings amount:

- For Fixed: Enter dollar amount (e.g., 50.00)
- For Percentage: Enter percentage (e.g., 30)

**Example:**
```
Savings Type: Percentage
Savings Value: 40

If a resource costs $100/month, the recommendation will show $40/month savings potential.
```

---

### Step 4: Define Conditions

Conditions determine which resources match the rule. All conditions must be met (AND logic).

**Available Condition Types:**

1. **name_is**
   - Resource name exactly matches value
   - Example: `name_is` = "test-server"

2. **name_starts_with**
   - Resource name starts with value
   - Example: `name_starts_with` = "dev-"

3. **name_ends_with**
   - Resource name ends with value
   - Example: `name_ends_with` = "-backup"

4. **name_contains**
   - Resource name contains value
   - Example: `name_contains` = "staging"

5. **resource_type_is**
   - Resource type matches value
   - Example: `resource_type_is` = "EC2 Instance"

6. **cloud_is**
   - Cloud provider matches value
   - Example: `cloud_is` = "aws" (or "azure", "gcp")

7. **region_is**
   - Region matches value
   - Example: `region_is` = "us-east-1"

8. **tag_is**
   - Tag key=value matches exactly
   - Example: `tag_is` = "environment=development"

9. **tag_exists**
   - Tag key exists (any value)
   - Example: `tag_exists` = "environment"

10. **tag_value_starts_with**
    - Tag value starts with prefix
    - Example: `tag_value_starts_with` = "team=backend"

**Adding Conditions:**

1. Click **"Add Condition"**
2. Select condition type from dropdown
3. Enter condition value
4. Repeat for additional conditions
5. All conditions are combined with AND logic

**Example Rule Conditions:**
```
Condition 1: tag_is "environment=development"
Condition 2: resource_type_is "EC2 Instance"
Condition 3: name_starts_with "dev-"

This matches: Development EC2 instances with names starting with "dev-"
```

---

### Step 5: Save Rule

- Click **"Create Rule"** to save
- Rule becomes active immediately
- Recommendations will appear on next scheduler run

---

## Editing a Rule

1. Click on the rule name in the list
2. Modify any field (name, description, conditions, etc.)
3. Click **"Save"**
4. Changes take effect immediately

**Note**: Editing a rule updates all existing recommendations generated by that rule.

---

## Enable/Disable a Rule

**From List View:**
- Click the **Enable/Disable** toggle
- Disabled rules won't generate new recommendations
- Existing recommendations remain until cache refresh

**From Edit View:**
- Toggle the **Active** switch
- Click **"Save"**

---

## Deleting a Rule

1. Click on the rule name
2. Click **"Delete"**
3. Confirm deletion
4. Rule and its recommendations are removed

**Note**: Existing recommendations from the rule will be removed on next refresh.

---

## Example Rules

### Rule 1: Idle Development Instances

**Name:** Identify idle development instances  
**Category:** Cost  
**Severity:** Medium  
**Savings Type:** Percentage  
**Savings Value:** 60  

**Conditions:**
```
tag_is: environment=development
resource_type_is: EC2 Instance
```

**Description:** Finds development EC2 instances that may be idle or underutilized. Consider stopping or terminating these instances to save ~60% of costs.

---

### Rule 2: Unencrypted Production Storage

**Name:** Unencrypted production storage buckets  
**Category:** Security  
**Severity:** Critical  
**Savings Type:** Fixed  
**Savings Value:** 0  

**Conditions:**
```
tag_is: environment=production
resource_type_is: S3 Bucket
name_contains: data
```

**Description:** Production S3 buckets containing data should have encryption enabled. Enable server-side encryption to comply with security best practices.

---

### Rule 3: Single AZ Deployments

**Name:** Single availability zone resources  
**Category:** Reliability  
**Severity:** High  
**Savings Type:** Fixed  
**Savings Value:** 0  

**Conditions:**
```
tag_is: environment=production
cloud_is: aws
region_is: us-east-1
```

**Description:** Production resources in a single availability zone are at risk of outages. Deploy across multiple AZs for high availability.

---

### Rule 4: Missing Team Tags

**Name:** Resources missing team ownership tags  
**Category:** Operational Excellence  
**Severity:** Medium  
**Savings Type:** Fixed  
**Savings Value:** 0  

**Conditions:**
```
tag_exists: environment
tag_is: environment=production
```

**Description:** Production resources should have team ownership tags for cost allocation. Add "team" tag to enable chargeback reporting.

---

## Best Practices

### Rule Design

1. **Be Specific**: Use multiple conditions to avoid false positives
2. **Test First**: Create rules with narrow conditions and expand gradually
3. **Use Tags**: Leverage tagging for precise targeting
4. **Name Patterns**: Use name conventions consistently to enable rule matching
5. **Document**: Write clear descriptions explaining when to apply the rule

### Rule Organization

1. **Naming Convention**: Use consistent naming (e.g., "[Category] Description")
2. **Categories**: Use categories consistently for filtering
3. **Severity**: Align severity with actual business impact
4. **Savings**: Be realistic about savings estimates

### Rule Maintenance

1. **Review Quarterly**: Audit rules for relevance
2. **Disable Unused**: Disable rules that are no longer applicable
3. **Update Conditions**: Adjust conditions as infrastructure evolves
4. **Monitor Impact**: Track how many recommendations each rule generates

---

## API Endpoints

### Create Recommendation Rule
```
POST /api/v1/organizations/{org_id}/recommendation-rules
```

**Request Body:**
```json
{
  "name": "Identify idle development instances",
  "description": "Finds development EC2 instances with low utilization",
  "category": "cost",
  "severity": "medium",
  "saving_type": "percentage",
  "saving_value": 60.0,
  "conditions": [
    {
      "type": "tag_is",
      "meta_info": {
        "key": "environment",
        "value": "development"
      }
    },
    {
      "type": "resource_type_is",
      "meta_info": {
        "value": "EC2 Instance"
      }
    }
  ]
}
```

### List Recommendation Rules
```
GET /api/v1/organizations/{org_id}/recommendation-rules
```

### Get Single Rule
```
GET /api/v1/recommendation-rules/{rule_id}
```

### Update Rule
```
PATCH /api/v1/recommendation-rules/{rule_id}
```

### Delete Rule
```
DELETE /api/v1/recommendation-rules/{rule_id}
```

---

## Troubleshooting

### Rule Not Generating Recommendations

**Possible Causes:**
1. Rule is inactive/disabled
2. No resources match to conditions
3. Scheduler hasn't run yet
4. Conditions too restrictive

**Solutions:**
1. Verify rule status is "Active"
2. Review conditions and test against known resources
3. Wait for next scheduler run or trigger manually
4. Broaden conditions if too narrow

### Recommendations Appear Incorrect

**Validation:**
1. Check which resources match the conditions
2. Verify savings estimates are realistic
3. Review description for accuracy
4. Adjust conditions or savings as needed

### Can't Edit or Delete Rule

**Permissions:**
- You need appropriate permissions (Engineer or Admin role)
- Contact your Organization Admin if you lack permissions

---

## Next Steps

- **[Recommendations](recommendations.md)** - View generated recommendations
- **[Rules Engine](rules-engine.md)** - Auto-assign resources to pools
- **[Schedulers](schedulers.md)** - Configure recommendation generation
- **[Resources](resources.md)** - View resources matching your rules

---

**Related Documentation:**
- [How to Configure Recommendation Rules](guides/configure-recommendation-rules.md)
- [API Reference](api-reference.md)
