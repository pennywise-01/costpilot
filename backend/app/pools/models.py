from sqlalchemy import BigInteger, Boolean, Integer, String, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import PoolPurpose, ConstraintType


class Pool(BaseModel, OptimisticLockingMixin):
    __tablename__ = "pools"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    limit: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pools.id"), nullable=True, index=True
    )
    purpose: Mapped[PoolPurpose] = mapped_column(
        SAEnum(
            PoolPurpose,
            name="poolpurpose",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=PoolPurpose.BUDGET,
        nullable=False,
    )
    default_owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=True
    )

    children = relationship(
        "Pool",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    parent = relationship(
        "Pool",
        back_populates="children",
        remote_side="Pool.id",
        lazy="joined",
    )
    policies = relationship(
        "PoolPolicy",
        back_populates="pool",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PoolPolicy(BaseModel, OptimisticLockingMixin):
    __tablename__ = "pool_policies"

    type: Mapped[ConstraintType] = mapped_column(
        SAEnum(ConstraintType, name="constrainttype", values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    limit: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pool_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pools.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )

    pool = relationship("Pool", back_populates="policies")
