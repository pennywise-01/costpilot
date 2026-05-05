"""Config findings service.

Orchestrates the per-account config snapshot pipeline:

    cloud_account_config
        -> config_ingestors[].fetch()        # bulk resource inventory calls
        -> ResourceConfigSnapshot rows persisted  # one observed_at per scan

Callable from a scheduled job (see `scheduler/executor.py`) and from
an ad-hoc API trigger (see `router.py`).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cloud_accounts.models import CloudAccount
from app.config_ingestors.factory import get_config_ingestors_for
from app.config_ingestors.models import ResourceConfigSnapshot
from app.config_ingestors.schemas import NormalizedResourceConfig
from app.shared.crypto import decrypt
from app.shared.retry import RetryConfig, with_retry

logger = logging.getLogger(__name__)


async def collect_config_snapshots_for_org(
    db: AsyncSession,
    org_id: str,
    cloud_account_ids: list[str] | None = None,
) -> int:
    """Run config ingestion for every eligible cloud account in an org.

    Returns total resource snapshots persisted across all accounts.
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
            "No cloud accounts eligible for config ingestion in org %s", org_id
        )
        return 0

    observed_at = datetime.now(timezone.utc)
    total = 0
    for account in accounts:
        try:
            count = await _scan_account(db, account, observed_at)
            total += count
        except Exception:
            logger.exception(
                "Config scan failed for account %s (org %s)",
                account.id, org_id,
            )
    return total


async def _scan_account(
    db: AsyncSession, account: CloudAccount, observed_at: datetime,
) -> int:
    """Scan one cloud account and persist its config snapshots."""
    ingestors = get_config_ingestors_for(account.type)
    if not ingestors:
        logger.debug(
            "No config ingestors registered for cloud type %s", account.type
        )
        return 0

    try:
        config = json.loads(decrypt(account.config))
    except Exception:
        logger.warning("Invalid config for cloud account %s", account.id)
        return 0

    all_resources: list[NormalizedResourceConfig] = []
    retry_config = RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0)
    for ingestor in ingestors:
        try:
            items = await with_retry(
                ingestor.fetch, retry_config, config,
            )
            all_resources.extend(items)
        except Exception:
            logger.warning(
                "Config ingestor %s failed after retries for account %s",
                ingestor.source_service, account.id,
            )

    if not all_resources:
        return 0

    return await persist_snapshots(db, account, all_resources, observed_at)


async def persist_snapshots(
    db: AsyncSession,
    account: CloudAccount,
    resources: Iterable[NormalizedResourceConfig],
    observed_at: datetime,
) -> int:
    """Persist a batch of resource config snapshots for one account.

    Idempotent against the unique index (cloud_account_id, resource_id,
    observed_at) — repeated calls with the same observed_at silently skip
    duplicates instead of raising.
    """
    inserted = 0
    for r in resources:
        row = ResourceConfigSnapshot(
            organization_id=account.organization_id,
            cloud_account_id=account.id,
            cloud=r.cloud,
            account_id=r.account_id,
            source_service=r.source_service,
            resource_id=r.resource_id,
            resource_type=r.resource_type,
            region=r.region,
            properties=r.properties,
            tags=r.tags,
            observed_at=observed_at,
        )
        db.add(row)
        inserted += 1

    try:
        await db.flush()
    except Exception:
        await db.rollback()
        logger.warning(
            "Persist batch failed for account %s; some snapshots may already exist",
            account.id,
        )
        return 0

    logger.info(
        "Persisted %d config snapshots for account %s at %s",
        inserted, account.id, observed_at.isoformat(),
    )
    return inserted


async def list_snapshots_for_org(
    db: AsyncSession,
    org_id: str,
    resource_type: str | None = None,
    limit: int = 500,
) -> list[ResourceConfigSnapshot]:
    """List the most recent config snapshots for an organization, optionally
    scoped to a specific resource type.
    """
    query = select(ResourceConfigSnapshot).where(
        ResourceConfigSnapshot.organization_id == org_id,
    )
    if resource_type:
        query = query.where(ResourceConfigSnapshot.resource_type == resource_type)
    query = query.order_by(ResourceConfigSnapshot.observed_at.desc()).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())
