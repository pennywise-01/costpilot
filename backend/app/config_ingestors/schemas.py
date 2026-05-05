"""Pydantic schemas for the config_ingestors module (Tier-2 inventory)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedResourceConfig(BaseModel):
    """In-memory resource-config record emitted by a config ingestor.

    One record per cloud resource. The `properties` dict carries the
    full configuration (type-dependent), and downstream rules/SQL
    views derive rule evaluations from it.
    """

    cloud: str
    account_id: str
    source_service: str
    resource_id: str
    resource_type: str
    region: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=datetime.utcnow)


class ResourceConfigSnapshotResponse(BaseModel):
    """API response model for config snapshots."""

    id: str
    organization_id: str
    cloud_account_id: str
    cloud: str
    account_id: str
    source_service: str
    resource_id: str
    resource_type: str
    region: str
    properties: dict[str, Any] | None = None
    tags: dict[str, Any] | None = None
    observed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
