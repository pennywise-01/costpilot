"""Pydantic schemas for the advisor_findings module."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedAdvisorFinding(BaseModel):
    """In-memory finding emitted by an ingestor before persistence.

    Mirrors the AdvisorFinding ORM model fields that the ingestor knows
    about. `builtin_rule_id` is filled in by the service via
    `mapping.resolve_builtin_rule_id`, not by the ingestor itself.
    """

    cloud: str
    account_id: str
    source_service: str
    finding_type: str
    resource_id: str = ""
    region: str = ""
    severity: str = "medium"
    estimated_saving: float = 0.0
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class AdvisorFindingResponse(BaseModel):
    """API response model."""

    id: str
    organization_id: str
    cloud_account_id: str
    cloud: str
    account_id: str
    source_service: str
    finding_type: str
    resource_id: str
    region: str
    severity: str
    estimated_saving: float
    builtin_rule_id: str | None
    observed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
