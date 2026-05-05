"""SQLAlchemy model for the `advisor_findings` table.

One row per finding emitted by a cloud-provider advisor API
(Compute Optimizer / Trusted Advisor / Cost Optimization Hub /
Azure Advisor / GCP Recommender).

Schema mirrors the plan in plans/rule-data-source-strategy.md:
    cloud, account_id, finding_type, resource_id, region,
    severity, estimated_saving, raw_payload, observed_at.

Stored in Postgres (alongside the rest of CostPilot's metadata).
The plan's "BigQuery table" terminology is generic — the canonical
findings store for CostPilot is Postgres.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DECIMAL,
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


class AdvisorFinding(Base):
    """A single advisor / recommender finding.

    Append-only: ingestors write a fresh batch per scan, deduped by
    `(cloud_account_id, finding_type, resource_id, observed_at)`.
    Old rows are kept as a history trail for trend analysis.
    """

    __tablename__ = "advisor_findings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
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

    # The finding itself
    finding_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    estimated_saving: Mapped[float] = mapped_column(
        DECIMAL(15, 2), nullable=False, default=0,
    )
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Mapped built-in rule (resolved at ingest time via mapping.py).
    # Nullable: ingestor may emit findings whose type isn't yet mapped.
    builtin_rule_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
    )

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
        # Idempotency: one row per (account, finding_type, resource, observation)
        UniqueConstraint(
            "cloud_account_id", "finding_type", "resource_id", "observed_at",
            name="uix_advisor_findings_dedup",
        ),
        # Fast lookup by org + rule (rule evaluation path)
        Index("idx_advisor_findings_org_rule", "organization_id", "builtin_rule_id"),
        # Fast lookup of latest scan for an account
        Index("idx_advisor_findings_account_observed", "cloud_account_id", "observed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AdvisorFinding("
            f"cloud={self.cloud}, type={self.finding_type}, "
            f"resource={self.resource_id[:32]}, saving=${self.estimated_saving}"
            f")>"
        )
