from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.enums import RolePurpose
from app.shared.models import BaseModel, OptimisticLockingMixin


class Organization(BaseModel, OptimisticLockingMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    pool_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pools.id"), nullable=True
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employees: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="organization", lazy="selectin"
    )
    cloud_accounts: Mapped[list["CloudAccount"]] = relationship(
        "CloudAccount", back_populates="organization", lazy="selectin"
    )
    scheduler_configs: Mapped[list["SchedulerConfig"]] = relationship(
        "SchedulerConfig", back_populates="organization", lazy="selectin"
    )
    cost_caches: Mapped[list["CostCache"]] = relationship(
        "CostCache", back_populates="organization", lazy="selectin"
    )
    cost_cache_status: Mapped["CostCacheStatus"] = relationship(
        "CostCacheStatus", back_populates="organization", lazy="selectin"
    )


class Employee(BaseModel, OptimisticLockingMixin):
    __tablename__ = "employees"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False
    )
    auth_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[RolePurpose] = mapped_column(
        SAEnum(
            RolePurpose,
            name="rolepurpose",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=RolePurpose.MEMBER,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(128), nullable=True)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="employees", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint(
            "auth_user_id", "organization_id",
            name="uq_employee_user_org",
        ),
    )
