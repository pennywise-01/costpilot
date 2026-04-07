"""Default RBAC roles and permissions for new organizations."""

from app.shared.enums import PermissionAction, RBACResourceType

# Default roles configuration for new organizations
DEFAULT_ROLES = [
    {
        "name": "Organization Admin",
        "description": "Full administrative control across all organization resources.",
        "is_default": True,
        "permissions": [
            # Organization management
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.ORGANIZATION},
            # User management
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.USER},
            # Cloud accounts
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            # Pools
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.POOL},
            # Expenses
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.EXPENSE},
            # Resources
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.RESOURCE},
            # Recommendations
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.RECOMMENDATION},
            # Rules
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.RULE},
            # Notifications
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.NOTIFICATION},
            # Enterprise features
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.ENTERPRISE},
        ],
    },
    {
        "name": "Admin View Only",
        "description": "Read-only visibility across organization and enterprise resources.",
        "is_default": True,
        "permissions": [
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ORGANIZATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.USER},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.POOL},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.EXPENSE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RESOURCE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RECOMMENDATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RULE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.NOTIFICATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ENTERPRISE},
        ],
    },
    {
        "name": "Engineer",
        "description": "Operational role for engineering workflows with limited write access.",
        "is_default": True,
        "permissions": [
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ORGANIZATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.USER},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            {"action": PermissionAction.CREATE, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            {"action": PermissionAction.UPDATE, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.POOL},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.EXPENSE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RESOURCE},
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.RECOMMENDATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RULE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.NOTIFICATION},
        ],
    },
    {
        "name": "Viewer",
        "description": "General read-only access for business stakeholders.",
        "is_default": True,
        "permissions": [
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ORGANIZATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.USER},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.POOL},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.EXPENSE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RESOURCE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RECOMMENDATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RULE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.NOTIFICATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ENTERPRISE},
        ],
    },
    {
        "name": "Billing Admin",
        "description": "Cost and billing operations role with expense management access.",
        "is_default": True,
        "permissions": [
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ORGANIZATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.USER},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.POOL},
            {"action": PermissionAction.MANAGE, "resource_type": RBACResourceType.EXPENSE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RESOURCE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RECOMMENDATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.NOTIFICATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ENTERPRISE},
        ],
    },
    {
        "name": "Security Auditor",
        "description": "Read-only role for security and compliance review workflows.",
        "is_default": True,
        "permissions": [
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ORGANIZATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.USER},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.CLOUD_ACCOUNT},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.POOL},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.EXPENSE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RESOURCE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RECOMMENDATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.RULE},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.NOTIFICATION},
            {"action": PermissionAction.READ, "resource_type": RBACResourceType.ENTERPRISE},
        ],
    },
]

# Built-in role names are reserved and cannot be used for custom roles.
SYSTEM_ROLE_NAMES = tuple(role["name"] for role in DEFAULT_ROLES)

# Legacy names for migration and compatibility lookups.
LEGACY_ROLE_RENAMES = {
    "Organization Owner": "Organization Admin",
    "Finance": "Billing Admin",
}

# Role automatically assigned to organization creators.
OWNER_ROLE_NAME = "Organization Admin"
OWNER_ROLE_ALIASES = (
    OWNER_ROLE_NAME,
    "Organization Owner",
)
