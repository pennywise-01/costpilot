# SQLAlchemy Enum Mismatch - Complete Codebase Audit

**Date:** April 9, 2026  
**Severity:** 🔴 **CRITICAL** - 15 columns will fail on INSERT/UPDATE  
**Status:** 📋 **AUDIT COMPLETE** - Fixes needed

---

## Executive Summary

**15 out of 19 enum columns** have the same mismatch issue as the AWS connection error. These will ALL fail when trying to insert or update data with the same error:

```
invalid input value for enum <enum_name>: "<UPPER_CASE_NAME>"
```

---

## Complete Mismatch List

| # | Model | Column | Enum Class | Member Name | DB Value | Status |
|---|-------|--------|-----------|-------------|----------|--------|
| 1 | SecurityEvent | event_type | SecurityEventType | SESSION_VALIDATION_FAILED | session_validation_failed | ❌ |
| 2 | SessionBinding | revoke_reason | SessionRevokeReason | MANUAL_LOGOUT | manual_logout | ❌ |
| 3 | PoolPolicy | type | ConstraintType | TTL | ttl | ❌ |
| 4 | Condition | type | ConditionType | NAME_IS | name_is | ❌ |
| 5 | RecommendationRule | severity | RecommendationSeverity | CRITICAL | critical | ❌ |
| 6 | RecommendationRule | saving_type | SavingType | FIXED | fixed | ❌ |
| 7 | RecommendationRuleCondition | type | ConditionType | NAME_IS | name_is | ❌ |
| 8 | NotificationPreference | notification_type | NotificationType | BUDGET_ALERTS | budget_alerts | ❌ |
| 9 | NotificationLog | notification_type | NotificationType | BUDGET_ALERTS | budget_alerts | ❌ |
| 10 | RolePermission | action | PermissionAction | READ | read | ❌ |
| 11 | RolePermission | resource_type | RBACResourceType | ORGANIZATION | organization | ❌ |
| 12 | ABACPolicy | resource_type | RBACResourceType | ORGANIZATION | organization | ❌ |
| 13 | ABACPolicy | action | PermissionAction | READ | read | ❌ |
| 14 | ABACPolicy | operator | ABACOperator | EQUALS | equals | ❌ |
| 15 | AccessReview | status | AccessReviewStatus | PENDING | pending | ❌ |

---

## Safe Columns (Already Have values_callable)

| # | Model | Column | Enum Class | Status |
|---|-------|--------|-----------|--------|
| 1 | CloudAccount | type | CloudType | ✅ SAFE |
| 2 | User | role | RolePurpose | ✅ SAFE |
| 3 | Employee | role | RolePurpose | ✅ SAFE |
| 4 | Pool | purpose | PoolPurpose | ✅ SAFE |

---

## Impact Assessment

### High-Risk Features (Will Fail)

| Feature | Affected Operations | User Impact |
|---------|-------------------|-------------|
| **Security Events** | Logging security events | Security audit trail broken |
| **Session Management** | Session revocation | Session tracking broken |
| **Pool Policies** | Creating policies | Budget/alert policies can't be created |
| **Rules Engine** | Creating rule conditions | Custom rules broken |
| **Recommendations** | Creating recommendation rules | Optimization recommendations broken |
| **Notifications** | Setting notification preferences | Users can't configure notifications |
| **RBAC** | Creating roles/policies | Permission management broken |
| **Access Reviews** | Starting reviews | Compliance reviews broken |

### Why This Wasn't Caught Earlier

1. **These features may not have been tested end-to-end** with real database inserts
2. **Some features are enterprise-only** (RBAC, access reviews, notifications) and may not have test coverage
3. **The error only occurs on INSERT/UPDATE**, not SELECT (so existing data can be read)
4. **No integration tests** for these specific create/update operations

---

## Fix Strategy

All 15 columns need the same fix pattern:

```python
# BEFORE (will fail):
type: Mapped[ConditionType] = mapped_column(SAEnum(ConditionType), nullable=False)

# AFTER (working):
type: Mapped[ConditionType] = mapped_column(
    SAEnum(ConditionType, values_callable=lambda e: [x.value for x in e]),
    nullable=False
)
```

---

## Files to Fix

1. `backend/app/auth/models.py` - 2 columns (SecurityEvent, SessionBinding)
2. `backend/app/pools/models.py` - 1 column (PoolPolicy)
3. `backend/app/rules/models.py` - 1 column (Condition)
4. `backend/app/recommendation_rules/models.py` - 3 columns (RecommendationRule x2, RecommendationRuleCondition)
5. `backend/app/notifications/models.py` - 2 columns (NotificationPreference, NotificationLog)
6. `backend/app/enterprise/modules/rbac/models.py` - 6 columns (RolePermission x2, ABACPolicy x3, AccessReview)

---

## Testing Plan

After fixing all columns:

1. **Test each feature individually:**
   - Create a security event
   - Revoke a session
   - Create a pool policy
   - Create a rule condition
   - Create a recommendation rule
   - Set notification preferences
   - Create RBAC role/permission
   - Start an access review

2. **Verify in database:**
   ```sql
   SELECT enum_column FROM table_name WHERE ...;
   -- Should show lowercase snake_case values, not UPPER_CASE
   ```

3. **Run validation script:**
   ```bash
   docker exec costpilot-backend-1 python /app/scripts/validate_data_integrity.py
   ```

---

## Priority

🔴 **CRITICAL** - Fix before any user tests these features

All 15 columns are **ticking time bombs** - they will fail the first time someone tries to create/update data in these features.

---

**Audit completed by:** Systematic Codebase Analysis  
**Date:** April 9, 2026  
**Next Step:** Apply fixes to all 15 affected columns
