from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, Enum as SAEnum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import (
    PermissionAction,
    RBACResourceType,
    ABACOperator,
    AccessReviewStatus,
)


class Role(BaseModel, OptimisticLockingMixin):
    __tablename__ = "rbac_roles"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("name", "organization_id", name="uq_role_name_org"),
    )


class RolePermission(BaseModel, OptimisticLockingMixin):
    __tablename__ = "rbac_role_permissions"

    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rbac_roles.id"), nullable=False, index=True
    )
    action: Mapped[PermissionAction] = mapped_column(
        SAEnum(PermissionAction, name="permissionaction", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    resource_type: Mapped[RBACResourceType] = mapped_column(
        SAEnum(RBACResourceType, name="rbacresourcetype", values_callable=lambda e: [x.value for x in e]), nullable=False
    )

    role: Mapped["Role"] = relationship("Role", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "action", "resource_type", name="uq_role_action_resource"),
    )


class UserRoleAssignment(BaseModel, OptimisticLockingMixin):
    __tablename__ = "rbac_user_roles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rbac_roles.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    assigned_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    role: Mapped["Role"] = relationship("Role", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "organization_id", name="uq_user_role_org"),
    )


class ABACPolicy(BaseModel, OptimisticLockingMixin):
    __tablename__ = "rbac_abac_policies"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    resource_type: Mapped[RBACResourceType] = mapped_column(
        SAEnum(RBACResourceType, name="rbacresourcetype", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    action: Mapped[PermissionAction] = mapped_column(
        SAEnum(PermissionAction, name="permissionaction", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    attribute_key: Mapped[str] = mapped_column(String(256), nullable=False)
    operator: Mapped[ABACOperator] = mapped_column(
        SAEnum(ABACOperator, name="abacoperator", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    attribute_value: Mapped[str] = mapped_column(Text, nullable=False)
    effect_allow: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AccessReview(BaseModel, OptimisticLockingMixin):
    __tablename__ = "rbac_access_reviews"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rbac_roles.id"), nullable=False
    )
    status: Mapped[AccessReviewStatus] = mapped_column(
        SAEnum(AccessReviewStatus, name="accessreviewstatus", values_callable=lambda e: [x.value for x in e]),
        default=AccessReviewStatus.PENDING,
        nullable=False
    )
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    role: Mapped["Role"] = relationship("Role", lazy="selectin")


class SSOConfig(BaseModel, OptimisticLockingMixin):
    __tablename__ = "rbac_sso_configs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)  # saml, oidc
    issuer_url: Mapped[str] = mapped_column(String(512), nullable=False)
    client_id: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    metadata_url: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_provision_roles: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_role_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rbac_roles.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_sso_org_provider"),
    )
