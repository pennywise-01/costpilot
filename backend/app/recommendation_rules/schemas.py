from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.enums import ConditionType, RecommendationSeverity, SavingType


class RecRuleConditionCreate(BaseModel):
    type: ConditionType
    meta_info: str | None = None


class RecRuleConditionResponse(BaseModel):
    id: str
    type: ConditionType
    meta_info: str | None = None

    model_config = {"from_attributes": True}


class RecRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    category: str = "cost"
    severity: RecommendationSeverity = RecommendationSeverity.MEDIUM
    action_description: str = ""
    saving_type: SavingType = SavingType.FIXED
    saving_value: float = 0.0
    conditions: list[RecRuleConditionCreate] = Field(default_factory=list)
    active: bool = True


class RecRuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = None
    category: str | None = None
    severity: RecommendationSeverity | None = None
    action_description: str | None = None
    saving_type: SavingType | None = None
    saving_value: float | None = None
    active: bool | None = None
    conditions: list[RecRuleConditionCreate] | None = None


class RecRuleResponse(BaseModel):
    id: str
    name: str
    description: str
    priority: int
    organization_id: str
    creator_id: str
    active: bool
    category: str
    severity: RecommendationSeverity
    action_description: str
    saving_type: SavingType
    saving_value: float
    conditions: list[RecRuleConditionResponse]
    created_at: datetime
    is_builtin: bool = False
    data_source: str = "billing"

    model_config = {"from_attributes": True}
