import enum


class CloudType(str, enum.Enum):
    # Cloud Service Providers (direct API)
    AWS = "aws_cnr"
    AZURE = "azure_cnr"
    AZURE_TENANT = "azure_tenant"
    GCP = "gcp_cnr"
    GCP_TENANT = "gcp_tenant"
    ALIBABA = "alibaba_cnr"
    KUBERNETES = "kubernetes_cnr"
    NEBIUS = "nebius"
    DATABRICKS = "databricks"
    # Big Data Analytics Platforms (query normalized tables)
    BIGQUERY = "bigquery"       # GCP BigQuery
    REDSHIFT = "redshift"       # AWS Redshift
    ATHENA = "athena"           # AWS Athena
    SYNAPSE = "synapse"         # Azure Synapse Analytics


class PoolPurpose(str, enum.Enum):
    BUDGET = "budget"
    BUSINESS_UNIT = "business_unit"
    TEAM = "team"
    PROJECT = "project"
    CICD = "cicd"
    MLAI = "mlai"
    ASSET_POOL = "asset_pool"


class ConstraintType(str, enum.Enum):
    TTL = "ttl"
    TOTAL_EXPENSE_LIMIT = "total_expense_limit"
    DAILY_EXPENSE_LIMIT = "daily_expense_limit"


class RolePurpose(str, enum.Enum):
    MEMBER = "optscale_member"
    ENGINEER = "optscale_engineer"
    MANAGER = "optscale_manager"


class ConditionType(str, enum.Enum):
    NAME_IS = "name_is"
    NAME_STARTS_WITH = "name_starts_with"
    NAME_ENDS_WITH = "name_ends_with"
    NAME_CONTAINS = "name_contains"
    RESOURCE_TYPE_IS = "resource_type_is"
    CLOUD_IS = "cloud_is"
    TAG_IS = "tag_is"
    REGION_IS = "region_is"
    TAG_EXISTS = "tag_exists"
    TAG_VALUE_STARTS_WITH = "tag_value_starts_with"


class ImportState(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class OrgConstraintType(str, enum.Enum):
    EXPENSE_ANOMALY = "expense_anomaly"
    EXPIRING_BUDGET = "expiring_budget"
    RECURRING_BUDGET = "recurring_budget"
    RESOURCE_COUNT_ANOMALY = "resource_count_anomaly"
    RESOURCE_QUOTA = "resource_quota"
    TAGGING_POLICY = "tagging_policy"


class RecommendationSource(str, enum.Enum):
    BUILTIN = "builtin"
    CUSTOM_RULE = "custom_rule"
    CSP_NATIVE = "csp_native"


class RecommendationSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SavingType(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class NotificationType(str, enum.Enum):
    BUDGET_ALERTS = "budget_alerts"
    RECOMMENDATION_UPDATES = "recommendation_updates"
    DAILY_COST_SUMMARY = "daily_cost_summary"
    WEEKLY_REPORT = "weekly_report"
    ANOMALY_ALERTS = "anomaly_alerts"
    NEW_USER_JOINED = "new_user_joined"


class PermissionAction(str, enum.Enum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MANAGE = "manage"


class RBACResourceType(str, enum.Enum):
    ORGANIZATION = "organization"
    CLOUD_ACCOUNT = "cloud_account"
    POOL = "pool"
    EXPENSE = "expense"
    RESOURCE = "resource"
    RECOMMENDATION = "recommendation"
    RULE = "rule"
    USER = "user"
    NOTIFICATION = "notification"
    ENTERPRISE = "enterprise"


class ABACOperator(str, enum.Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"


class AccessReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REVOKED = "revoked"


class ApiKeyScope(str, enum.Enum):
    RESOURCES_READ = "resources:read"
    RESOURCES_WRITE = "resources:write"
    EXPENSES_READ = "expenses:read"
    EXPENSES_WRITE = "expenses:write"
    RECOMMENDATIONS_READ = "recommendations:read"
    RECOMMENDATIONS_WRITE = "recommendations:write"
    POOLS_READ = "pools:read"
    POOLS_WRITE = "pools:write"
    CLOUD_ACCOUNTS_READ = "cloud_accounts:read"
    CLOUD_ACCOUNTS_WRITE = "cloud_accounts:write"
    FULL_ACCESS = "full_access"


class WebhookEvent(str, enum.Enum):
    RECOMMENDATION_CREATED = "recommendation.created"
    ANOMALY_DETECTED = "anomaly.detected"
    BUDGET_EXCEEDED = "budget.exceeded"
    EXPENSE_THRESHOLD = "expense.threshold"
    RESOURCE_CREATED = "resource.created"
    RESOURCE_DELETED = "resource.deleted"


class UserStatus(str, enum.Enum):
    """User account lifecycle states."""
    PENDING = "pending"          # Invited, not yet accepted
    ACTIVE = "active"            # Normal active state
    SUSPENDED = "suspended"      # Temporarily disabled by admin
    DEACTIVATED = "deactivated"  # Permanently disabled
    LOCKED = "locked"            # Auto-locked due to failed login attempts
