"""Azure Advisor ingestor.

Pulls recommendations from Azure Advisor (`Microsoft.Advisor/
recommendations`) for a subscription. Azure Advisor pre-scores
resources across Cost, Security, Performance, Reliability, and
Operational Excellence — we ingest the recommendation objects and let
the built-in rule engine map them to rules via
`app.advisor_findings.mapping.AZURE_ADVISOR_MAP`.

SDK: `azure-mgmt-advisor` (already vendored in the project's image).
Auth: reuses the stored CloudAccount config (tenant_id / client_id /
client_secret / subscription_id) via the standard
`ClientSecretCredential`.

Required Azure RBAC:
    - Reader (subscription or root management group scope) —
      Microsoft.Advisor/recommendations/read is included in Reader.
"""

import asyncio
import logging
from typing import Any

from app.advisor_findings.ingestors.base import AdvisorIngestor
from app.advisor_findings.schemas import NormalizedAdvisorFinding

logger = logging.getLogger(__name__)


# Azure Advisor's `impact` field maps cleanly to our severity scale.
# `Medium` is Azure's default for most recommendations.
_IMPACT_SEVERITY: dict[str, str] = {
    "High": "high",
    "Medium": "medium",
    "Low": "low",
}


class AzureAdvisorIngestor(AdvisorIngestor):
    """Pulls recommendations from Azure Advisor for one subscription."""

    source_service = "Azure Advisor"

    async def fetch(self, config: dict) -> list[NormalizedAdvisorFinding]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("Azure Advisor ingestion failed")
            return []

    # ------------------------------------------------------------------

    def _fetch_sync(self, config: dict) -> list[NormalizedAdvisorFinding]:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.advisor import AdvisorManagementClient

        tenant_id = config.get("tenant_id", "")
        client_id = config.get("client_id", "")
        client_secret = config.get("client_secret", "")
        subscription_id = config.get("subscription_id", "")
        if not all([tenant_id, client_id, client_secret, subscription_id]):
            logger.warning(
                "Azure Advisor: missing config keys for subscription %s",
                subscription_id or "<unknown>",
            )
            return []

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        client = AdvisorManagementClient(credential, subscription_id)

        findings: list[NormalizedAdvisorFinding] = []
        try:
            for rec in client.recommendations.list():
                finding = self._normalize(rec, subscription_id)
                if finding is not None:
                    findings.append(finding)
        except Exception as e:
            logger.warning(
                "Azure Advisor list() failed for subscription %s: %s",
                subscription_id, e,
            )
            return findings

        logger.info(
            "Azure Advisor ingest: %d recommendations for subscription %s",
            len(findings), subscription_id,
        )
        return findings

    @staticmethod
    def _normalize(rec: Any, subscription_id: str) -> NormalizedAdvisorFinding | None:
        """Convert a `ResourceRecommendationBase` to a normalized finding.

        Azure Advisor recommendations use these relevant fields:
            - category: Cost | Security | Performance | HighAvailability | OperationalExcellence
            - impact: High | Medium | Low
            - short_description.solution: human-readable action
            - resource_metadata.resource_id: full ARM resource ID
            - extended_properties: dict with type-specific fields
                (e.g. savingsAmount, recommendationType)

        Our `finding_type` follows the namespaced convention from
        mapping.py: `azure_advisor.<Category>.<RecommendationType>`.
        Unknown types still persist — they just won't drive a rule
        until a mapping is added.
        """
        try:
            category = getattr(rec, "category", "") or ""
            impact = getattr(rec, "impact", "") or ""

            extended = getattr(rec, "extended_properties", None) or {}
            rec_type = extended.get("recommendationType") or extended.get(
                "recommendationTypeId"
            ) or category

            resource_meta = getattr(rec, "resource_metadata", None)
            resource_id = (
                getattr(resource_meta, "resource_id", "") if resource_meta else ""
            ) or ""

            # Savings are reported as string dollars in extended_properties
            # (`savingsAmount`) on Cost recommendations. Other categories
            # don't expose a saving figure.
            estimated_saving = 0.0
            raw_saving = extended.get("savingsAmount") or extended.get(
                "annualSavingsAmount"
            )
            if raw_saving:
                try:
                    estimated_saving = float(raw_saving)
                except (TypeError, ValueError):
                    estimated_saving = 0.0

            return NormalizedAdvisorFinding(
                cloud="azure_cnr",
                account_id=subscription_id,
                source_service="Azure Advisor",
                finding_type=f"azure_advisor.{category}.{rec_type}",
                resource_id=resource_id,
                region=_region_from_resource_id(resource_id),
                severity=_IMPACT_SEVERITY.get(impact, "medium"),
                estimated_saving=estimated_saving,
                raw_payload={
                    "category": category,
                    "impact": impact,
                    "recommendation_type": rec_type,
                    "short_description": _short_description(rec),
                    "extended_properties": {
                        k: v for k, v in extended.items()
                        # Strip anything that looks like a secret/token.
                        if not any(kw in k.lower() for kw in ("key", "secret", "token"))
                    },
                },
            )
        except Exception as e:
            # Per-recommendation errors are tolerated — we'd rather
            # persist 99/100 than fail the whole scan.
            logger.debug("Failed to normalize Azure Advisor rec: %s", e)
            return None


def _region_from_resource_id(resource_id: str) -> str:
    """Azure ARM IDs don't embed region. Advisor exposes it separately,
    but since we don't always have it, fall back to empty string.
    Downstream rules can still key off finding_type + resource_id."""
    return ""


def _short_description(rec: Any) -> str:
    """Extract the `short_description.solution` string if present."""
    desc = getattr(rec, "short_description", None)
    if desc is None:
        return ""
    solution = getattr(desc, "solution", "") or ""
    problem = getattr(desc, "problem", "") or ""
    return solution or problem
