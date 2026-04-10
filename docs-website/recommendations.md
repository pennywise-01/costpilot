# Recommendations

![Recommendations Page](screenshots/recommendations-page.png)

Discover and act on AI-powered cost optimization recommendations.

---

## Overview

The Recommendations page provides intelligent suggestions to optimize your cloud spending, improve security, enhance reliability, and boost performance.

**URL**: `/recommendations`

**Key Features:**
- AI-powered optimization suggestions
- Multiple categories (Cost, Security, Reliability, Performance, Operational Excellence)
- Filter by category, source, and cloud provider
- Potential savings tracking
- Affected resource counts
- Built-in and custom recommendations
- Dismiss irrelevant suggestions

---

## Page Layout

### Summary Cards

At the top, recommendation summary by category:

**Categories:**
- **Cost**: Direct cost reduction opportunities
- **Security**: Security improvements and risk reduction
- **Reliability**: Reliability and availability enhancements
- **Performance**: Performance optimization suggestions
- **Operational Excellence**: Operational efficiency improvements

Each card shows:
- **Category Name** and icon
- **Potential Savings**: Total savings if all recommendations in category are implemented
- **Recommendation Count**: Number of recommendations in category
- **Cloud Providers**: Which providers have recommendations

---

### Filters

Filter recommendations using the controls at the top:

**Category:**
- All categories
- Cost
- Security
- Reliability
- Performance
- Operational Excellence

**Source:**
- All sources
- Built-in: Recommendations from CostPilot's built-in engine
- Custom Rules: Recommendations from your custom rules
- CSP Native: Native recommendations from cloud providers

**Cloud Provider:**
- All providers
- AWS
- Azure
- GCP

**Search:**
- Free-text search by recommendation title or description

---

### Recommendations List

Each recommendation card displays:

**Header:**
- **Recommendation Title**: Brief description of the suggestion
- **Category Badge**: Category icon and label
- **Severity Badge**: Critical, High, Medium, or Low
- **Source Badge**: Built-in, Custom, or CSP Native
- **Cloud Provider Icons**: Affected cloud providers

**Details:**
- **Description**: Detailed explanation of the recommendation
- **Potential Savings**: Estimated cost savings (if applicable)
- **Affected Resources**: Number of resources impacted
- **Supported Cloud Types**: AWS, Azure, GCP

**Actions:**
- **View Details**: Click to see full recommendation with affected resources
- **Dismiss**: Mark as not applicable (won't show again)
- **Undismiss**: Restore dismissed recommendations (filter toggle)

---

## Recommendation Detail Page

Click on a recommendation to view details:

**Recommendation Info:**
- **Title**: Full recommendation title
- **Category**: Recommendation category
- **Severity**: Priority level
- **Description**: Detailed explanation
- **Potential Savings**: Cost savings estimate
- **Cloud Providers**: Affected providers

**Affected Resources:**
- List of specific resources that can be optimized
- Resource name, type, and current cost
- Links to resource detail pages

**Implementation Guidance:**
- Step-by-step instructions (when available)
- Links to cloud provider documentation
- Best practices and considerations

**Actions:**
- **Dismiss**: Mark as not relevant
- **Clear Cache**: Force refresh of recommendations

---

## Recommendation Categories Explained

### Cost Recommendations

Suggestions to directly reduce cloud spending:

**Common Examples:**
- **Right-sizing**: Downsize over-provisioned instances
- **Idle Resources**: Terminate or stop unused resources
- **Reserved Instances**: Purchase RIs for steady-state workloads
- **Savings Plans**: Commit to usage-based discounts
- **Storage Optimization**: Move infrequently accessed data to cheaper tiers
- **Spot Instances**: Use spot instances for fault-tolerant workloads

**Impact:**
- Potential savings: 10-70% of affected resource costs
- Priority based on savings amount and effort required

### Security Recommendations

Suggestions to improve security posture:

**Common Examples:**
- **Unencrypted Storage**: Enable encryption on S3 buckets, databases
- **Public Access**: Remove public access from resources that should be private
- **IAM Policies**: Tighten overly permissive IAM policies
- **Security Groups**: Restrict inbound/outbound rules
- **MFA**: Enable multi-factor authentication
- **Key Rotation**: Rotate encryption keys regularly

**Impact:**
- Reduced risk of data breaches and compliance violations
- Improved security audit results

### Reliability Recommendations

Suggestions to enhance availability and fault tolerance:

**Common Examples:**
- **Single AZ Deployment**: Deploy across multiple availability zones
- **No Backup**: Enable automated backups for databases
- **No Auto-Scaling**: Add auto-scaling for variable workloads
- **Single Point of Failure**: Eliminate SPOFs in architecture
- **Health Checks**: Add health checks and monitoring

**Impact:**
- Improved uptime and availability
- Faster disaster recovery
- Better user experience

### Performance Recommendations

Suggestions to optimize performance:

**Common Examples:**
- **Instance Type**: Upgrade to newer instance families
- **Caching**: Add caching layers (Redis, Memcached)
- **CDN**: Use Content Delivery Network for static assets
- **Database Indexing**: Optimize database queries and indexes
- **Connection Pooling**: Implement connection pooling for databases

**Impact:**
- Faster response times
- Better resource utilization
- Improved user satisfaction

### Operational Excellence Recommendations

Suggestions to improve operational efficiency:

**Common Examples:**
- **Tagging**: Add missing tags for better cost tracking
- **Automation**: Automate manual operational tasks
- **Monitoring**: Add missing monitoring and alerting
- **Documentation**: Document operational procedures
- **Cost Allocation**: Implement chargeback/showback

**Impact:**
- Reduced operational overhead
- Better visibility and accountability
- Easier troubleshooting

---

## API Endpoints

### Get Recommendations Overview
```
GET /api/v1/organizations/{org_id}/recommendations?cloud_account_id[]=
```

**Query Parameters:**
- `cloud_account_id[]` (array): Filter by cloud account IDs

**Response:**
```json
{
  "summary": [
    {
      "category": "cost",
      "total_savings": 1250.00,
      "count": 15,
      "cloud_types": ["aws", "azure"]
    },
    {
      "category": "security",
      "total_savings": 0,
      "count": 8,
      "cloud_types": ["aws", "gcp"]
    }
  ],
  "total_savings": 1250.00,
  "total_count": 23
}
```

### Get Recommendations by Type
```
GET /api/v1/organizations/{org_id}/recommendations/{rec_type}
```

**Path Parameters:**
- `rec_type` (string): `cost`, `security`, `reliability`, `performance`, `operational_excellence`

**Response:**
```json
{
  "category": "cost",
  "recommendations": [
    {
      "id": "rec-uuid",
      "title": "Downsize underutilized EC2 instances",
      "description": "5 EC2 instances have average CPU utilization below 10%",
      "severity": "high",
      "source": "built-in",
      "potential_savings": 450.00,
      "affected_resources": 5,
      "cloud_types": ["aws"],
      "resources": [
        {
          "id": "i-123abc",
          "name": "dev-server-01",
          "type": "EC2 Instance",
          "current_cost": 120.00,
          "recommended_action": "Downsize from t3.large to t3.small"
        }
      ]
    }
  ],
  "total_savings": 450.00
}
```

### Dismiss Recommendation
```
PATCH /api/v1/organizations/{org_id}/recommendations/{rec_id}/dismiss
```

**Request Body:**
```json
{
  "dismissed": true
}
```

### Clear Recommendation Cache
```
POST /api/v1/organizations/{org_id}/recommendations/clear-cache?cloud_account_id=
```

**Query Parameters:**
- `cloud_account_id` (string): Clear cache for specific account

---

## Configuration

### Cache TTL

```python
# Recommendations Cache TTL (seconds)
CACHE_TTL_RECOMMENDATIONS = 600  # 10 minutes
```

### Recommendation Engine

Recommendations are generated by:
1. **Built-in Engine**: Analyzes resource utilization and costs
2. **Custom Rules**: User-defined rules (see Recommendation Rules documentation)
3. **CSP Native**: Native recommendations from cloud providers (when available)

---

## Best Practices

### Acting on Recommendations

1. **Start with High-Impact Items**
   - Focus on recommendations with highest savings
   - Prioritize Critical and High severity items

2. **Review Affected Resources**
   - Understand which resources are impacted
   - Verify recommendations are applicable to your use case

3. **Test in Non-Production First**
   - Implement changes in dev/staging before production
   - Monitor impact before and after changes

4. **Track Implemented Recommendations**
   - Document what you've implemented
   - Measure actual savings achieved
   - Share learnings with the team

5. **Dismiss Irrelevant Items**
   - Dismiss recommendations that don't apply
   - Reduces noise in future reviews
   - Keeps focus on actionable items

### Recommendation Review Cadence

- **Weekly**: Review new high-severity recommendations
- **Monthly**: Full recommendation review with team
- **Quarterly**: Comprehensive optimization review with stakeholders

---

## Troubleshooting

### No Recommendations Appear

**Possible Causes:**
1. Cloud accounts recently connected (analysis in progress)
2. Recommendation scheduler not running
3. All recommendations dismissed
4. Cache needs refresh

**Solutions:**
1. Wait for scheduler to run (check **Schedulers** page)
2. Clear recommendation cache manually
3. Check if recommendations are filtered out or dismissed
4. Verify cloud accounts are healthy and have cost data

### Recommendations Seem Incorrect

**Validation Steps:**
1. Review recommendation details and affected resources
2. Verify resource utilization in cloud provider console
3. Check if recommendation applies to your specific use case
4. Dismiss if not applicable to your situation

**Note**: Recommendations are suggestions based on general best practices. Always validate against your specific requirements before implementing.

### Stale Recommendations

**Clear Cache:**
```
POST /api/v1/organizations/{org_id}/recommendations/clear-cache
```

**Or via UI:**
- Click **"Clear Cache"** button on recommendations page
- Wait a moment for recommendations to refresh

---

## Next Steps

- **[Recommendation Rules](recommendation-rules.md)** - Create custom recommendation rules
- **[Resources](resources.md)** - View affected resources
- **[Dashboard](dashboard.md)** - See potential savings on dashboard
- **[Data Export](exports.md)** - Export recommendations for reporting

---

**Related Documentation:**
- [Overview](overview.md)
- [How to Configure Recommendation Rules](guides/configure-recommendation-rules.md)
- [API Reference](api-reference.md)
