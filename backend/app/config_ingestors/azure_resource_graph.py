"""Azure Resource Graph ingestor (Tier-2 asset/state inventory).

Queries Azure Resource Graph with KQL to enumerate resources across
the subscription (or management group) and normalizes each into
`NormalizedResourceConfig`.

SDK: `azure-mgmt-resource` (already vendored).
Auth: reuses CloudAccount config (tenant_id / client_id /
client_secret / subscription_id).

Required RBAC: `Reader` on the subscription (already part of
the config-tier role assignments).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.config_ingestors.base import ConfigIngestor
from app.config_ingestors.schemas import NormalizedResourceConfig

logger = logging.getLogger(__name__)

_KQL_QUERY = """
resources
| project
    id,
    name,
    type,
    location,
    tags,
    properties
"""


class AzureResourceGraphIngestor(ConfigIngestor):
    """Queries Azure Resource Graph for resource inventory."""

    source_service = "Azure Resource Graph"

    async def fetch(self, config: dict) -> list[NormalizedResourceConfig]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("Azure Resource Graph ingestion failed")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedResourceConfig]:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import ResourceGraphClient
        from azure.mgmt.resource.resourcegraph.models import QueryRequest

        tenant_id = config.get("tenant_id", "")
        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")
        subscription_id = config.get("subscription_id", "")
        if not all([tenant_id, client_id, client_secret, subscription_id]):
            logger.warning(
                "Azure Resource Graph: missing config keys for subscription %s",
                subscription_id or "<unknown>",
            )
            return []

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        client = ResourceGraphClient(credential)
        observed_at = datetime.now(timezone.utc)
        results: list[NormalizedResourceConfig] = []

        try:
            request = QueryRequest(
                query=_KQL_QUERY,
                subscriptions=[subscription_id],
            )
            response = client.resources(request)

            for row in response.data:
                results.append(NormalizedResourceConfig(
                    cloud="azure_cnr",
                    account_id=subscription_id,
                    source_service=self.source_service,
                    resource_id=row.get("id", ""),
                    resource_type=row.get("type", ""),
                    region=row.get("location", ""),
                    properties=row.get("properties", {}) or {},
                    tags=row.get("tags", {}) or {},
                    observed_at=observed_at,
                ))
        except Exception as e:
            logger.warning(
                "Azure Resource Graph query failed for subscription %s: %s",
                subscription_id, e,
            )

        logger.info(
            "Azure Resource Graph ingest: %d resources for subscription %s",
            len(results), subscription_id,
        )
        return results
