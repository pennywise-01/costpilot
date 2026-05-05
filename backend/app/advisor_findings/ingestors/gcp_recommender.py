"""GCP Recommender ingestor.

Pulls recommendations from the GCP Recommender API across the standard
recommenders that map to CostPilot built-in rules. GCP's Recommender
pre-scores resources (COST, SECURITY, PERFORMANCE, RELIABILITY,
MANAGEABILITY, SUSTAINABILITY) and we ingest the recommendations
individually, mapping them to rules via
`app.advisor_findings.mapping.GCP_RECOMMENDER_MAP`.

SDK: `google-cloud-recommender` (already vendored).
Auth: reuses the stored CloudAccount config (project_id +
credentials_json or Application Default Credentials).

Required IAM: `roles/recommender.viewer` (or per-recommender viewer
roles) on the target project/organization.
"""

import asyncio
import json
import logging
from typing import Any

from app.advisor_findings.ingestors.base import AdvisorIngestor
from app.advisor_findings.schemas import NormalizedAdvisorFinding

logger = logging.getLogger(__name__)

# Recommender → locations resolver. Zone recommenders must be queried
# in every zone the project uses; region recommenders in every region.
# `None` means the recommender is global and a single query suffices.
_RECOMMENDERS: dict[str, str | None] = {
    "google.compute.instance.IdleResourceRecommender": "zone",
    "google.compute.instance.MachineTypeRecommender": "zone",
    "google.compute.commitment.UsageCommitmentRecommender": "region",
    "google.compute.address.IdleResourceRecommender": "region",
    "google.iam.policy.Recommender": None,
}

# GCP Recommender impact category → severity
_IMPACT_SEVERITY: dict[str, str] = {
    "COST": "medium",
    "SECURITY": "high",
    "PERFORMANCE": "medium",
    "RELIABILITY": "high",
    "MANAGEABILITY": "low",
    "SUSTAINABILITY": "low",
}

# GCP regions (subset of the full list, covering common zones).
# The ingestor queries the zone-level recommenders in each of these
# regions × standard `-a`, `-b`, `-c` zone suffixes.
_GCP_REGIONS = [
    "us-central1", "us-east1", "us-east4", "us-west1", "us-west2",
    "us-west3", "us-west4", "northamerica-northeast1",
    "europe-west1", "europe-west2", "europe-west3", "europe-west4",
    "europe-west6", "europe-north1", "asia-east1", "asia-east2",
    "asia-northeast1", "asia-northeast2", "asia-northeast3",
    "asia-southeast1", "asia-southeast2", "asia-south1", "asia-south2",
    "australia-southeast1", "southamerica-east1",
]

_GLOBAL_LOCATION = "global"


class GcpRecommenderIngestor(AdvisorIngestor):
    """Pulls recommendations from the GCP Recommender API."""

    source_service = "GCP Recommender"

    async def fetch(self, config: dict) -> list[NormalizedAdvisorFinding]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("GCP Recommender ingestion failed")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedAdvisorFinding]:
        from google.cloud import recommender_v1

        project_id = config.get("project_id", "")
        if not project_id:
            logger.warning("GCP Recommender: missing project_id in config")
            return []

        credentials = _get_credentials(config)
        if not credentials:
            return []

        client = recommender_v1.RecommenderClient(credentials=credentials)
        findings: list[NormalizedAdvisorFinding] = []

        for recommender_id, scope in _RECOMMENDERS.items():
            locations = _locations_for(recommender_id, scope)
            for location in locations:
                parent = f"projects/{project_id}/locations/{location}/recommenders/{recommender_id}"
                try:
                    req = recommender_v1.ListRecommendationsRequest(parent=parent)
                    for rec in client.list_recommendations(request=req):
                        finding = self._normalize(rec, project_id, recommender_id)
                        if finding is not None:
                            findings.append(finding)
                except Exception as e:
                    logger.debug(
                        "GCP Recommender: %s/%s failed: %s",
                        recommender_id, location, e,
                    )

        logger.info(
            "GCP Recommender ingest: %d recommendations for project %s",
            len(findings), project_id,
        )
        return findings

    @staticmethod
    def _normalize(
        rec: Any, project_id: str, recommender_id: str,
    ) -> NormalizedAdvisorFinding | None:
        try:
            subtype = getattr(rec, "recommender_subtype", "") or ""

            primary_impact = getattr(rec, "primary_impact", None)
            category = ""
            cost_projection = None
            if primary_impact:
                category = getattr(primary_impact, "category", "") or ""
                if hasattr(primary_impact, "cost_projection"):
                    cost_projection = primary_impact.cost_projection

            estimated_saving = 0.0
            if cost_projection:
                try:
                    cost = cost_projection.cost
                    currency = getattr(cost, "currency_code", "USD") or "USD"
                    units = int(getattr(cost, "units", 0) or 0)
                    nanos = int(getattr(cost, "nanos", 0) or 0)
                    estimated_saving = units + nanos / 1e9
                except (TypeError, ValueError, AttributeError):
                    estimated_saving = 0.0

            finding_type = (
                f"gcp_recommender.{recommender_id}.{subtype}"
                if subtype
                else f"gcp_recommender.{recommender_id}"
            )

            resource_name = getattr(rec, "name", "")
            etag = getattr(rec, "etag", "")

            return NormalizedAdvisorFinding(
                cloud="gcp_cnr",
                account_id=project_id,
                source_service="GCP Recommender",
                finding_type=finding_type,
                resource_id=resource_name,
                region="",
                severity=_IMPACT_SEVERITY.get(category, "medium"),
                estimated_saving=estimated_saving,
                raw_payload={
                    "recommender": recommender_id,
                    "subtype": subtype,
                    "category": category,
                    "description": getattr(rec, "description", ""),
                    "state": _recommendation_state(rec),
                    "etag": etag,
                },
            )
        except Exception as e:
            logger.debug("Failed to normalize GCP Recommender rec: %s", e)
            return None


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
        logger.warning("GCP Recommender: credential setup failed: %s", e)
        return None


def _locations_for(recommender_id: str, scope: str | None) -> list[str]:
    if scope is None:
        return [_GLOBAL_LOCATION]
    if scope == "region":
        return _GCP_REGIONS
    if scope == "zone":
        zones: list[str] = []
        for region in _GCP_REGIONS:
            for suffix in ("-a", "-b", "-c"):
                zones.append(f"{region}{suffix}")
        return zones
    return [_GLOBAL_LOCATION]


def _recommendation_state(rec: Any) -> str:
    state_info = getattr(rec, "state_info", None)
    if state_info is None:
        return ""
    return getattr(state_info, "state", "") or ""
