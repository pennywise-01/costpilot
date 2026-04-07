from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.enums import PoolPurpose, ConstraintType


class PoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    limit: int = 0
    parent_id: str | None = None
    purpose: PoolPurpose | None = None
    default_owner_id: str | None = None


class PoolUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    limit: int | None = None
    default_owner_id: str | None = None
    purpose: PoolPurpose | None = None


class PoolResponse(BaseModel):
    id: str
    name: str
    limit: int
    organization_id: str
    parent_id: str | None
    purpose: PoolPurpose
    default_owner_id: str | None
    created_at: datetime
    children: list[PoolResponse] = []
    # Real-time calculated fields
    spent: float = 0.0
    owner: str | None = None

    model_config = {"from_attributes": True}


class PoolPolicyCreate(BaseModel):
    type: ConstraintType
    limit: int
    active: bool = True


class PoolPolicyResponse(BaseModel):
    id: str
    type: ConstraintType
    limit: int
    active: bool
    pool_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
