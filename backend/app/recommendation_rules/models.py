from sqlalchemy import Boolean, Integer, Float, String, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, OptimisticLockingMixin
from app.shared.enums import ConditionType, RecommendationSeverity, SavingType


class RecommendationRule(BaseModel, OptimisticLockingMixin):
    __tablename__ = "recommendation_rules"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    creator_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="cost")
    severity: Mapped[RecommendationSeverity] = mapped_column(
        SAEnum(RecommendationSeverity), nullable=False, default=RecommendationSeverity.MEDIUM
    )
    action_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    saving_type: Mapped[SavingType] = mapped_column(
        SAEnum(SavingType), nullable=False, default=SavingType.FIXED
    )
    saving_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    conditions: Mapped[list["RecommendationRuleCondition"]] = relationship(
        "RecommendationRuleCondition", back_populates="rule", lazy="selectin"
    )


class RecommendationRuleCondition(BaseModel, OptimisticLockingMixin):
    __tablename__ = "recommendation_rule_conditions"

    type: Mapped[ConditionType] = mapped_column(SAEnum(ConditionType), nullable=False)
    rule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recommendation_rules.id"), nullable=False
    )
    meta_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    rule: Mapped["RecommendationRule"] = relationship(
        "RecommendationRule", back_populates="conditions"
    )
