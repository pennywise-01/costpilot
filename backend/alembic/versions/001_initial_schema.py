"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def _base_columns():
    """Columns shared by every table via BaseModel."""
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    ]


# --------------- enum types (Postgres native) ---------------

role_purpose = sa.Enum(
    "optscale_member", "optscale_engineer", "optscale_manager",
    name="rolepurpose",
)
cloud_type = sa.Enum(
    "aws_cnr", "azure_cnr", "azure_tenant", "gcp_cnr", "gcp_tenant",
    "alibaba_cnr", "kubernetes_cnr", "environment", "nebius", "databricks",
    name="cloudtype",
)
pool_purpose = sa.Enum(
    "budget", "business_unit", "team", "project", "cicd", "mlai", "asset_pool",
    name="poolpurpose",
)
constraint_type = sa.Enum(
    "ttl", "total_expense_limit", "daily_expense_limit",
    name="constrainttype",
)
condition_type = sa.Enum(
    "name_is", "name_starts_with", "name_ends_with", "name_contains",
    "resource_type_is", "cloud_is", "tag_is", "region_is",
    "tag_exists", "tag_value_starts_with",
    name="conditiontype",
)
recommendation_severity = sa.Enum(
    "critical", "high", "medium", "low",
    name="recommendationseverity",
)
saving_type = sa.Enum(
    "fixed", "percentage",
    name="savingtype",
)
notification_type = sa.Enum(
    "budget_alerts", "recommendation_updates", "daily_cost_summary",
    "weekly_report", "anomaly_alerts", "new_user_joined",
    name="notificationtype",
)
permission_action = sa.Enum(
    "read", "create", "update", "delete", "manage",
    name="permissionaction",
)
rbac_resource_type = sa.Enum(
    "organization", "cloud_account", "pool", "expense", "resource",
    "recommendation", "rule", "user", "notification", "enterprise",
    name="rbacresourcetype",
)
abac_operator = sa.Enum(
    "equals", "not_equals", "in", "not_in", "contains", "starts_with",
    name="abacoperator",
)
access_review_status = sa.Enum(
    "pending", "approved", "revoked",
    name="accessreviewstatus",
)


def upgrade() -> None:
    # ---- users ----
    op.create_table(
        "users",
        *_base_columns(),
        sa.Column("email", sa.String(256), unique=True, index=True, nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("verified", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("role", role_purpose, nullable=False),
        sa.Column("last_login", sa.DateTime, nullable=True),
    )

    # ---- organizations ----
    op.create_table(
        "organizations",
        *_base_columns(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("pool_id", sa.String(36), nullable=True),  # FK added later
        sa.Column("is_demo", sa.Boolean, server_default="false", nullable=False),
        sa.Column("disabled", sa.Boolean, server_default="false", nullable=False),
    )

    # ---- employees ----
    op.create_table(
        "employees",
        *_base_columns(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("auth_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", role_purpose, nullable=False),
    )

    # ---- pools ----
    op.create_table(
        "pools",
        *_base_columns(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("limit", sa.BigInteger, server_default="0", nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("pools.id"), nullable=True, index=True),
        sa.Column("purpose", pool_purpose, nullable=False),
        sa.Column("default_owner_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=True),
    )

    # Now add FK from organizations.pool_id -> pools.id
    op.create_foreign_key(
        "fk_organizations_pool_id", "organizations", "pools",
        ["pool_id"], ["id"],
    )

    # ---- pool_policies ----
    op.create_table(
        "pool_policies",
        *_base_columns(),
        sa.Column("type", constraint_type, nullable=False),
        sa.Column("limit", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("pool_id", sa.String(36), sa.ForeignKey("pools.id"), nullable=False, index=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
    )

    # ---- cloud_accounts ----
    op.create_table(
        "cloud_accounts",
        *_base_columns(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("type", cloud_type, nullable=False),
        sa.Column("config", sa.Text, nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("auto_import", sa.Boolean, server_default="true", nullable=False),
        sa.Column("import_period", sa.Integer, server_default="1", nullable=False),
        sa.Column("last_import_at", sa.Integer, nullable=True),
        sa.Column("last_import_error", sa.Text, nullable=True),
        sa.Column("account_id", sa.String(256), nullable=False),
        sa.Column("process_recommendations", sa.Boolean, server_default="true", nullable=False),
    )

    # ---- rules ----
    op.create_table(
        "rules",
        *_base_columns(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("pool_id", sa.String(36), sa.ForeignKey("pools.id"), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("creator_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("active", sa.Boolean, server_default="true", nullable=False),
    )

    # ---- conditions ----
    op.create_table(
        "conditions",
        *_base_columns(),
        sa.Column("type", condition_type, nullable=False),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("meta_info", sa.Text, nullable=True),
    )

    # ---- recommendation_rules ----
    op.create_table(
        "recommendation_rules",
        *_base_columns(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, server_default="", nullable=False),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("creator_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("category", sa.String(64), server_default="cost", nullable=False),
        sa.Column("severity", recommendation_severity, nullable=False),
        sa.Column("action_description", sa.Text, server_default="", nullable=False),
        sa.Column("saving_type", saving_type, nullable=False),
        sa.Column("saving_value", sa.Float, server_default="0.0", nullable=False),
    )

    # ---- recommendation_rule_conditions ----
    op.create_table(
        "recommendation_rule_conditions",
        *_base_columns(),
        sa.Column("type", condition_type, nullable=False),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("recommendation_rules.id"), nullable=False),
        sa.Column("meta_info", sa.Text, nullable=True),
    )

    # ---- notification_preferences ----
    op.create_table(
        "notification_preferences",
        *_base_columns(),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("enabled", sa.Boolean, server_default="true", nullable=False),
    )

    # ---- notification_logs ----
    op.create_table(
        "notification_logs",
        *_base_columns(),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("recipient_email", sa.String(256), nullable=False),
        sa.Column("subject", sa.String(512), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )

    # ---- rbac_roles ----
    op.create_table(
        "rbac_roles",
        *_base_columns(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, server_default="", nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("is_default", sa.Boolean, server_default="false", nullable=False),
        sa.UniqueConstraint("name", "organization_id", name="uq_role_name_org"),
    )

    # ---- rbac_role_permissions ----
    op.create_table(
        "rbac_role_permissions",
        *_base_columns(),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("rbac_roles.id"), nullable=False, index=True),
        sa.Column("action", permission_action, nullable=False),
        sa.Column("resource_type", rbac_resource_type, nullable=False),
        sa.UniqueConstraint("role_id", "action", "resource_type", name="uq_role_action_resource"),
    )

    # ---- rbac_user_roles ----
    op.create_table(
        "rbac_user_roles",
        *_base_columns(),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("rbac_roles.id"), nullable=False, index=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.UniqueConstraint("user_id", "role_id", "organization_id", name="uq_user_role_org"),
    )

    # ---- rbac_abac_policies ----
    op.create_table(
        "rbac_abac_policies",
        *_base_columns(),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, server_default="", nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("resource_type", rbac_resource_type, nullable=False),
        sa.Column("action", permission_action, nullable=False),
        sa.Column("attribute_key", sa.String(256), nullable=False),
        sa.Column("operator", abac_operator, nullable=False),
        sa.Column("attribute_value", sa.Text, nullable=False),
        sa.Column("effect_allow", sa.Boolean, server_default="true", nullable=False),
        sa.Column("active", sa.Boolean, server_default="true", nullable=False),
    )

    # ---- rbac_access_reviews ----
    op.create_table(
        "rbac_access_reviews",
        *_base_columns(),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("rbac_roles.id"), nullable=False),
        sa.Column("status", access_review_status, nullable=False),
        sa.Column("notes", sa.Text, server_default="", nullable=False),
    )

    # ---- rbac_sso_configs ----
    op.create_table(
        "rbac_sso_configs",
        *_base_columns(),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("issuer_url", sa.String(512), nullable=False),
        sa.Column("client_id", sa.String(256), server_default="", nullable=False),
        sa.Column("metadata_url", sa.String(512), server_default="", nullable=False),
        sa.Column("enabled", sa.Boolean, server_default="false", nullable=False),
        sa.Column("auto_provision_roles", sa.Boolean, server_default="false", nullable=False),
        sa.Column("default_role_id", sa.String(36), sa.ForeignKey("rbac_roles.id"), nullable=True),
        sa.UniqueConstraint("organization_id", "provider", name="uq_sso_org_provider"),
    )


def downgrade() -> None:
    op.drop_table("rbac_sso_configs")
    op.drop_table("rbac_access_reviews")
    op.drop_table("rbac_abac_policies")
    op.drop_table("rbac_user_roles")
    op.drop_table("rbac_role_permissions")
    op.drop_table("rbac_roles")
    op.drop_table("notification_logs")
    op.drop_table("notification_preferences")
    op.drop_table("recommendation_rule_conditions")
    op.drop_table("recommendation_rules")
    op.drop_table("conditions")
    op.drop_table("rules")
    op.drop_table("cloud_accounts")
    op.drop_table("pool_policies")
    op.drop_constraint("fk_organizations_pool_id", "organizations", type_="foreignkey")
    op.drop_table("pools")
    op.drop_table("employees")
    op.drop_table("organizations")
    op.drop_table("users")

    # Drop enum types
    for e in [
        access_review_status, abac_operator, rbac_resource_type,
        permission_action, notification_type, saving_type,
        recommendation_severity, condition_type, constraint_type,
        pool_purpose, cloud_type, role_purpose,
    ]:
        e.drop(op.get_bind(), checkfirst=True)
