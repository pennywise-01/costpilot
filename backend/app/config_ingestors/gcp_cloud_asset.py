"""GCP Cloud Asset ingestor (Tier-2 asset/state inventory).

Enumerates resources in a GCP project (or across projects in an org)
and normalizes each into `NormalizedResourceConfig`.

Uses the Cloud Asset Inventory API (`google-api-python-client`) which
is already vendored. The native `Cloud Asset → BigQuery export` path
is a one-Terraform-resource setup; this ingestor provides a
programmatic pull path for users without BigQuery.

Auth: reuses CloudAccount config (project_id + credentials_json or
Application Default Credentials).

Required IAM: `roles/cloudasset.viewer` on the target project.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config_ingestors.base import ConfigIngestor
from app.config_ingestors.schemas import NormalizedResourceConfig

logger = logging.getLogger(__name__)

_ASSET_TYPES: list[str] = [
    "compute.googleapis.com/Instance",
    "compute.googleapis.com/Disk",
    "compute.googleapis.com/Address",
    "compute.googleapis.com/ForwardingRule",
    "sqladmin.googleapis.com/Instance",
    "storage.googleapis.com/Bucket",
    "bigquery.googleapis.com/Dataset",
    "bigquery.googleapis.com/Table",
    "iam.googleapis.com/ServiceAccount",
]


class GcpCloudAssetIngestor(ConfigIngestor):
    """Lists cloud assets from GCP Cloud Asset Inventory."""

    source_service = "GCP Cloud Asset"

    async def fetch(self, config: dict) -> list[NormalizedResourceConfig]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("GCP Cloud Asset ingestion failed")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedResourceConfig]:
        project_id = config.get("project_id", "")
        if not project_id:
            logger.warning("GCP Cloud Asset: missing project_id in config")
            return []

        credentials = _get_credentials(config)
        if not credentials:
            return []

        from googleapiclient.discovery import build

        service = build("cloudasset", "v1", credentials=credentials)
        observed_at = datetime.now(timezone.utc)
        results: list[NormalizedResourceConfig] = []

        for asset_type in _ASSET_TYPES:
            try:
                request = service.assets().list(
                    parent=f"projects/{project_id}",
                    assetTypes=[asset_type],
                    contentType="RESOURCE",
                    pageSize=500,
                )
                while request is not None:
                    response = request.execute()
                    for asset in response.get("assets", []):
                        resource = asset.get("resource", {})
                        resource_data = resource.get("data", {}) or {}
                        name = asset.get("name", "")

                        results.append(NormalizedResourceConfig(
                            cloud="gcp_cnr",
                            account_id=project_id,
                            source_service=self.source_service,
                            resource_id=name,
                            resource_type=asset_type,
                            region=resource.get("location", "") or "",
                            properties=resource_data,
                            tags=resource.get("labels", {}) or {},
                            observed_at=observed_at,
                        ))
                    request = service.assets().list_next(request, response)
            except Exception as e:
                logger.debug(
                    "GCP Cloud Asset: list failed for %s: %s",
                    asset_type, e,
                )

        logger.info(
            "GCP Cloud Asset ingest: %d resources for project %s",
            len(results), project_id,
        )
        return results


def _get_credentials(config: dict) -> Any:
    try:
        from google.oauth2 import service_account
        from google.auth import default as google_auth_default

        credentials_json = config.get("credentials_json", "")
        if credentials_json:
            info = json.loads(credentials_json)
            return service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        creds, _ = google_auth_default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return creds
    except Exception as e:
        logger.warning("GCP Cloud Asset: credential setup failed: %s", e)
        return None
