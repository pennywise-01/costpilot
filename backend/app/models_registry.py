"""Central model registry for SQLAlchemy metadata discovery.

All models are imported here so that ``Base.metadata`` knows about every
table.  ``main.py`` only needs to import this single module instead of
15 individual model imports from 12 different packages.

To add a new model, add its import here — do NOT modify ``main.py``.
"""

# Auth & Users
from app.auth.models import User  # noqa: F401
from app.user_management.models import UserInvitation, UserActivityLog, UserPreferences  # noqa: F401

# Organizations
from app.organizations.models import Organization, Employee  # noqa: F401

# Cloud Accounts
from app.cloud_accounts.models import CloudAccount  # noqa: F401

# Pools & Budgets
from app.pools.models import Pool, PoolPolicy  # noqa: F401

# Rules
from app.rules.models import Rule, Condition  # noqa: F401
from app.recommendation_rules.models import RecommendationRule, RecommendationRuleCondition  # noqa: F401

# Notifications
from app.notifications.models import NotificationPreference, NotificationLog  # noqa: F401

# Enterprise / RBAC
from app.enterprise.modules.rbac.models import (  # noqa: F401
    Role, RolePermission, UserRoleAssignment, ABACPolicy, AccessReview, SSOConfig,
)

# Scheduler
from app.scheduler.models import SchedulerConfig, SchedulerRun, SchedulerLog  # noqa: F401

# Export
from app.enterprise.modules.export.models import ExportTemplate, ExportJob, ScheduledExport  # noqa: F401

# Dashboards
from app.dashboards.models import Dashboard  # noqa: F401

# Security
from app.security.models import AuditLog, SecurityAlert  # noqa: F401

# Idempotency
from app.idempotency.models import IdempotencyKey  # noqa: F401

# Advisor Findings
from app.advisor_findings.models import AdvisorFinding  # noqa: F401
