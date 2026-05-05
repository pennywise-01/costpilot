"""Advisor findings service.

Orchestrates the per-account scan pipeline:

    cloud_account_config
        -> ingestors[].fetch()              # bulk advisor API calls
        -> mapping.resolve_builtin_rule_id  # finding_type -> builtin-NNN
        -> AdvisorFinding rows persisted    # one observed_at per scan

The service is callable both from a scheduled job (see `scheduler/executor.py`)
and from an ad-hoc API trigger (see `router.py`).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.advisor_findings.ingestors.factory import get_ingestors_for
from app.advisor_findings.mapping import resolve_builtin_rule_id
from app.advisor_findings.models import AdvisorFinding
from app.advisor_findings.schemas import NormalizedAdvisorFinding
from app.cloud_accounts.models import CloudAccount
from app.shared.crypto import decrypt
from app.shared.retry import RetryConfig, with_retry

logger = logging.getLogger(__name__)


async def collect_advisor_findings_for_org(
    db: AsyncSession,
    org_id: str,
    cloud_account_ids: list[str] | None = None,
) -> int:
    """Run advisor ingestion for every eligible cloud account in an org.

    Returns total findings persisted across all accounts.
    """
    query = select(CloudAccount).where(
        CloudAccount.organization_id == org_id,
        CloudAccount.process_recommendations.is_(True),
        CloudAccount.deleted_at.is_(None),
    )
    if cloud_account_ids:
        query = query.where(CloudAccount.id.in_(cloud_account_ids))

    result = await db.execute(query)
    accounts = list(result.scalars().all())

    if not accounts:
        logger.debug(
            "No cloud accounts eligible for advisor ingestion in org %s", org_id
        )
        return 0

    observed_at = datetime.now(timezone.utc)
    total = 0
    for account in accounts:
        try:
            count = await _scan_account(db, account, observed_at)
            total += count
        except Exception:
            # Per-account isolation: one bad account doesn't fail the org scan.
            logger.exception(
                "Advisor scan failed for account %s (org %s)",
                account.id, org_id,
            )
    return total


async def _scan_account(
    db: AsyncSession, account: CloudAccount, observed_at: datetime,
) -> int:
    """Scan one cloud account and persist its findings."""
    ingestors = get_ingestors_for(account.type)
    if not ingestors:
        logger.debug(
            "No advisor ingestors registered for cloud type %s", account.type
        )
        return 0

    try:
        config = json.loads(decrypt(account.config))
    except Exception:
        logger.warning("Invalid config for cloud account %s", account.id)
        return 0

    all_findings: list[NormalizedAdvisorFinding] = []
    retry_config = RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0)
    for ingestor in ingestors:
        try:
            items = await with_retry(
                ingestor.fetch, retry_config, config,
            )
            all_findings.extend(items)
        except Exception:
            logger.warning(
                "Ingestor %s failed after retries for account %s",
                ingestor.source_service, account.id,
            )

    if not all_findings:
        return 0

    return await persist_findings(db, account, all_findings, observed_at)


async def persist_findings(
    db: AsyncSession,
    account: CloudAccount,
    findings: Iterable[NormalizedAdvisorFinding],
    observed_at: datetime,
) -> int:
    """Persist a batch of findings for one account.

    Idempotent against the unique index `(cloud_account_id, finding_type,
    resource_id, observed_at)` — repeated calls with the same `observed_at`
    silently skip duplicates instead of raising.
    """
    inserted = 0
    for f in findings:
        rule_id = resolve_builtin_rule_id(f.finding_type)
        row = AdvisorFinding(
            organization_id=account.organization_id,
            cloud_account_id=account.id,
            cloud=f.cloud,
            account_id=f.account_id,
            source_service=f.source_service,
            finding_type=f.finding_type,
            resource_id=f.resource_id,
            region=f.region,
            severity=f.severity,
            estimated_saving=f.estimated_saving,
            raw_payload=f.raw_payload,
            builtin_rule_id=rule_id,
            observed_at=observed_at,
        )
        db.add(row)
        inserted += 1

    try:
        await db.flush()
    except Exception:
        # Most likely cause: unique-constraint violation on a duplicate
        # observation. Roll back this batch and continue.
        await db.rollback()
        logger.warning(
            "Persist batch failed for account %s; some findings may already exist",
            account.id,
        )
        return 0

    logger.info(
        "Persisted %d advisor findings for account %s at %s",
        inserted, account.id, observed_at.isoformat(),
    )
    return inserted


async def list_findings_for_org(
    db: AsyncSession,
    org_id: str,
    builtin_rule_id: str | None = None,
    limit: int = 500,
) -> list[AdvisorFinding]:
    """List the most recent findings for an organization, optionally
    scoped to a specific built-in rule.
    """
    query = select(AdvisorFinding).where(
        AdvisorFinding.organization_id == org_id,
    )
    if builtin_rule_id:
        query = query.where(AdvisorFinding.builtin_rule_id == builtin_rule_id)
    query = query.order_by(AdvisorFinding.observed_at.desc()).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())
