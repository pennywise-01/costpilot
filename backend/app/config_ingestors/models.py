"""SQLAlchemy model for the `resource_config_snapshots` table.

One row per cloud resource captured during a daily config snapshot.
Append-only: each scan writes a fresh batch keyed by `observed_at`.
Old rows are kept for drift detection and trend analysis.

Schema mirrors the Tier-2 plan in plans/rule-data-source-strategy.md.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class ResourceConfigSnapshot(Base):
    """A single resource-configuration record from a config ingestor.

    Append-only: ingestors write a fresh batch per scan, deduped by
    (cloud_account_id, resource_id, observed_at).
    """

    __tablename__ = "resource_config_snapshots"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid,
    )

    # Org / account scoping
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    cloud_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cloud_accounts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Provider identity
    cloud: Mapped[str] = mapped_column(String(32), nullable=False)
    account_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_service: Mapped[str] = mapped_column(String(64), nullable=False)

    # Resource identity
    resource_id: Mapped[str] = mapped_column(String(512), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # Resource configuration snapshot
    properties: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    # Relationships
    organization = relationship("Organization")
    cloud_account = relationship("CloudAccount")

    __table_args__ = (
        UniqueConstraint(
            "cloud_account_id", "resource_id", "observed_at",
            name="uix_config_snapshots_dedup",
        ),
        Index("idx_config_snapshots_org", "organization_id"),
        Index("idx_config_snapshots_account", "cloud_account_id"),
        Index("idx_config_snapshots_type", "resource_type"),
        Index("idx_config_snapshots_account_observed", "cloud_account_id", "observed_at"),
    )
