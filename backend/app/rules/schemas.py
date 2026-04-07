from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.enums import ConditionType
from app.shared.pagination import PaginatedResponse


class ConditionCreate(BaseModel):
    type: ConditionType
    meta_info: str | None = None


class ConditionResponse(BaseModel):
    id: str
    type: ConditionType
    meta_info: str | None = None

    model_config = {"from_attributes": True}


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    pool_id: str
    # SEC-20: owner_id is set server-side from authenticated user
    conditions: list[ConditionCreate] = Field(default_factory=list)
    active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    pool_id: str | None = None
    # SEC-20: owner_id transfer requires server-side authorization
    active: bool | None = None
    conditions: list[ConditionCreate] | None = None


class RuleResponse(BaseModel):
    id: str
    name: str
    priority: int
    organization_id: str
    pool_id: str
    owner_id: str
    active: bool
    conditions: list[ConditionResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedRules(PaginatedResponse[RuleResponse]):
    """Paginated response for rules list."""
    pass
