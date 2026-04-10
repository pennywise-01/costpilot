# Rules Engine

Automatically assign resources to budget pools based on matching conditions.

---

## Overview

The Rules Engine evaluates resources against defined rules and automatically assigns them to budget pools and owners based on matching conditions.

**URL**: `/rules` (Note: Backend API available, dedicated UI page may vary)

**Key Features:**
- Automated resource-to-pool assignment
- Priority-based rule evaluation
- Flexible condition types
- Owner assignment
- Active/inactive toggle
- Soft delete support

---

## How It Works

1. **Define Rules**: Create rules with conditions and target pool/owner
2. **Set Priority**: Rules are evaluated in priority order (lower number = higher priority)
3. **Resource Evaluation**: When a resource is discovered, rules are evaluated
4. **Assignment**: First matching rule assigns the resource to its pool and owner
5. **Cost Attribution**: Resource costs appear under the assigned pool in reports

---

## Rule Structure

Each rule consists of:

**Metadata:**
- **Name**: Descriptive rule name
- **Priority**: Evaluation order (1 = highest priority)
- **Pool**: Target budget pool for matching resources
- **Owner**: User to assign as resource owner
- **Active**: Enable/disable toggle
- **Creator**: User who created the rule

**Conditions:**
- List of conditions that resources must match
- All conditions must be met (AND logic)
- Various condition types available

---

## Condition Types

The Rules Engine supports the same condition types as Recommendation Rules:

1. **name_is**: Resource name exactly matches
2. **name_starts_with**: Resource name starts with prefix
3. **name_ends_with**: Resource name ends with suffix
4. **name_contains**: Resource name contains substring
5. **resource_type_is**: Resource type matches
6. **cloud_is**: Cloud provider matches
7. **region_is**: Region matches
8. **tag_is**: Tag key=value matches
9. **tag_exists**: Tag key exists
10. **tag_value_starts_with**: Tag value starts with prefix

---

## Creating a Rule

### Via API

```
POST /api/v1/organizations/{org_id}/rules
```

**Request Body:**
```json
{
  "name": "Assign production EC2 to Engineering pool",
  "priority": 10,
  "pool_id": "pool-uuid-here",
  "owner_id": "user-uuid-here",
  "active": true,
  "conditions": [
    {
      "type": "tag_is",
      "meta_info": {
        "key": "environment",
        "value": "production"
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

**Notes:**
- `creator_id` and `owner_id` are set server-side based on authenticated user
- `priority` determines evaluation order
- Lower priority number = higher precedence

---

## Rule Evaluation Logic

### Priority Order

Rules are evaluated in ascending priority order:
- Priority 1 is evaluated first
- Priority 10 is evaluated after priority 5
- First matching rule wins (subsequent rules are not evaluated for that resource)

### Example

```
Rule 1: priority=1, condition: name_starts_with="prod-", pool="Production"
Rule 2: priority=5, condition: tag_is="environment=production", pool="Production"
Rule 3: priority=10, condition: cloud_is="aws", pool="AWS Pool"

Resource: "prod-web-server-01" (AWS EC2, environment=production)

Evaluation:
1. Rule 1 matches (name starts with "prod-")
2. Resource assigned to Production pool
3. Rules 2 and 3 are not evaluated for this resource
```

### Best Practice for Priority

- **Priority 1-10**: Specific rules (exact name matches, critical resources)
- **Priority 11-50**: Tag-based rules (environment, team, project)
- **Priority 51-100**: Broad rules (cloud provider, region)
- **Priority 100+**: Catch-all rules (default assignments)

---

## Use Cases

### 1. Environment-Based Assignment

**Rule:** Assign resources to pools based on environment tag

```json
{
  "name": "Production resources",
  "priority": 10,
  "pool_id": "<production-pool-id>",
  "conditions": [
    {
      "type": "tag_is",
      "meta_info": {
        "key": "environment",
        "value": "production"
      }
    }
  ]
}
```

---

### 2. Team-Based Assignment

**Rule:** Assign resources to team pools based on team tag

```json
{
  "name": "Backend team resources",
  "priority": 20,
  "pool_id": "<backend-team-pool-id>",
  "owner_id": "<backend-lead-user-id>",
  "conditions": [
    {
      "type": "tag_is",
      "meta_info": {
        "key": "team",
        "value": "backend"
      }
    }
  ]
}
```

---

### 3. Project-Based Assignment

**Rule:** Assign resources to project pools based on name pattern

```json
{
  "name": "Project Alpha resources",
  "priority": 15,
  "pool_id": "<project-alpha-pool-id>",
  "conditions": [
    {
      "type": "name_starts_with",
      "meta_info": {
        "value": "alpha-"
      }
    }
  ]
}
```

---

### 4. Cloud Provider Default

**Rule:** Default assignment for untagged AWS resources

```json
{
  "name": "Default AWS assignment",
  "priority": 100,
  "pool_id": "<aws-default-pool-id>",
  "conditions": [
    {
      "type": "cloud_is",
      "meta_info": {
        "value": "aws"
      }
    }
  ]
}
```

---

## Managing Rules

### List Rules

```
GET /api/v1/organizations/{org_id}/rules?page=1&page_size=50
```

**Response:**
```json
{
  "rules": [
    {
      "id": "rule-uuid",
      "name": "Production resources",
      "priority": 10,
      "pool_id": "pool-uuid",
      "pool_name": "Production",
      "owner_id": "user-uuid",
      "owner_name": "John Doe",
      "creator_id": "user-uuid",
      "active": true,
      "conditions_count": 2,
      "created_at": "2026-04-01T10:00:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 50
}
```

### Get Single Rule

```
GET /api/v1/rules/{rule_id}
```

### Update Rule

```
PATCH /api/v1/rules/{rule_id}
```

**Request Body:**
```json
{
  "name": "Updated rule name",
  "priority": 15,
  "pool_id": "new-pool-uuid",
  "owner_id": "new-user-uuid",
  "active": true,
  "conditions": [
    {
      "type": "tag_is",
      "meta_info": {
        "key": "environment",
        "value": "staging"
      }
    }
  ]
}
```

### Delete Rule

```
DELETE /api/v1/rules/{rule_id}
```

Performs a soft delete (rule is marked inactive but not removed from database).

---

## Best Practices

### Rule Design

1. **Start Specific**: Create specific rules with higher priority first
2. **Add Defaults Last**: Add broad catch-all rules with lower priority
3. **Use Tags**: Tag-based rules are more maintainable than name patterns
4. **Document**: Write clear rule names and descriptions
5. **Test**: Verify rules match expected resources before deploying

### Priority Management

1. **Leave Gaps**: Use priorities 10, 20, 30 (not 1, 2, 3) to allow insertion
2. **Document Priority**: Comment why a rule has its priority
3. **Review Regularly**: Audit rules quarterly for relevance
4. **Disable vs Delete**: Disable rules instead of deleting to preserve history

### Tagging Strategy

1. **Enforce Tags**: Require critical tags (environment, team, project)
2. **Consistent Values**: Standardize tag values (e.g., always "production" not "prod")
3. **Automate Tagging**: Use infrastructure-as-code to apply tags automatically
4. **Audit Tags**: Regularly review tagging compliance

---

## Troubleshooting

### Resource Not Assigned to Pool

**Possible Causes:**
1. No rules match the resource
2. Rules are inactive
3. Priority order causing unexpected matches
4. Resource doesn't meet condition criteria

**Solutions:**
1. Review resource attributes (name, tags, type, cloud, region)
2. Check if any rules should match (test conditions manually)
3. Create a specific rule for the resource
4. Ensure rules are active

### Resource Assigned to Wrong Pool

**Possible Causes:**
1. Higher priority rule matching unexpectedly
2. Conditions too broad
3. Outdated rule

**Solutions:**
1. Review rule priority order
2. Add more specific conditions to narrow matches
3. Create a higher-priority rule for the specific resource
4. Test conditions against resource attributes

### Rules Not Being Evaluated

**Check:**
1. Scheduler is running and processing resources
2. Rules are marked as active
3. Backend logs for rule evaluation errors

**Trigger Manual Evaluation:**
- Restart resource collection scheduler
- Or manually reassign resources via API

---

## API Reference

### Condition Object Structure

```json
{
  "type": "tag_is",
  "rule_id": "rule-uuid",
  "meta_info": {
    "key": "environment",
    "value": "production"
  }
}
```

**Condition Types and Meta Info:**

| Condition Type | Meta Info Keys | Example |
|----------------|----------------|---------|
| name_is | value | `{"value": "prod-server"}` |
| name_starts_with | value | `{"value": "prod-"}` |
| name_ends_with | value | `{"value": "-backup"}` |
| name_contains | value | `{"value": "staging"}` |
| resource_type_is | value | `{"value": "EC2 Instance"}` |
| cloud_is | value | `{"value": "aws"}` |
| region_is | value | `{"value": "us-east-1"}` |
| tag_is | key, value | `{"key": "env", "value": "prod"}` |
| tag_exists | key | `{"key": "environment"}` |
| tag_value_starts_with | key, value | `{"key": "team", "value": "backend"}` |

---

## Next Steps

- **[Pools](pools.md)** - Set up budget pools for resource assignment
- **[Recommendation Rules](recommendation-rules.md)** - Create custom recommendation rules
- **[Resources](resources.md)** - View discovered resources
- [Schedulers](schedulers.md)** - Configure automated processing

---

**Related Documentation:**
- [How to Create Budget Pools](guides/create-budget-pools.md)
- [API Reference](api-reference.md)
