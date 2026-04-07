from sqlalchemy import String, Integer, Boolean, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import ConditionType


class Rule(BaseModel, OptimisticLockingMixin):
    __tablename__ = "rules"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False
    )
    pool_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pools.id"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False
    )
    creator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    conditions: Mapped[list["Condition"]] = relationship(
        "Condition", back_populates="rule", lazy="selectin"
    )


class Condition(BaseModel, OptimisticLockingMixin):
    __tablename__ = "conditions"

    type: Mapped[ConditionType] = mapped_column(SAEnum(ConditionType), nullable=False)
    rule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rules.id"), nullable=False
    )
    meta_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    rule: Mapped["Rule"] = relationship("Rule", back_populates="conditions")
