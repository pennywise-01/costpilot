"""AWS Cost Optimization Hub ingestor.

Pulls recommendations from the Cost Optimization Hub API
(`cost-optimization-hub:ListRecommendations`). COH aggregates
recommendations from Compute Optimizer, Trusted Advisor, S3
Storage Lens, and other AWS services into a single normalized
API surface.

Required IAM (read-only):
    cost-optimization-hub:ListRecommendations
    cost-optimization-hub:GetRecommendation
"""

import asyncio
import logging
from typing import Any

from app.advisor_findings.ingestors.base import AdvisorIngestor
from app.advisor_findings.schemas import NormalizedAdvisorFinding

logger = logging.getLogger(__name__)

# COH action types → our namespaced finding_type keys.
# Only action types that map to built-in rules are included.
_ACTION_TYPE_TO_FINDING_TYPE: dict[str, str] = {
    "RightSize": "cost_optimization_hub.RightSize",
    "Stop": "cost_optimization_hub.Stop",
    "Upgrade": "cost_optimization_hub.Upgrade",
    "PurchaseReservedInstances": "cost_optimization_hub.PurchaseReservedInstances",
    "PurchaseSavingsPlans": "cost_optimization_hub.PurchaseSavingsPlans",
    "MigrateToGraviton": "cost_optimization_hub.MigrateToGraviton",
    "Delete": "cost_optimization_hub.Delete",
}

# COH resource types → severity heuristic
_RESOURCE_TYPE_SEVERITY: dict[str, str] = {
    "Ec2Instance": "medium",
    "EbsVolume": "medium",
    "LambdaFunction": "medium",
    "EcsService": "medium",
    "RdsDbInstance": "high",
    "S3Bucket": "medium",
    "Ec2AutoScalingGroup": "medium",
    "Ec2ReservedInstances": "medium",
    "SavingsPlans": "medium",
}


class AwsCostOptimizationHubIngestor(AdvisorIngestor):
    """Pulls recommendations from AWS Cost Optimization Hub."""

    source_service = "AWS Cost Optimization Hub"

    async def fetch(self, config: dict) -> list[NormalizedAdvisorFinding]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("AWS Cost Optimization Hub ingestion failed")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedAdvisorFinding]:
        from app.cloud_accounts.adapters.aws import AWSAdapter

        primary_region = (
            config.get("region")
            or config.get("region_name")
            or "us-east-1"
        )
        adapter_config = {
            "access_key_id": config.get("access_key_id")
                or config.get("aws_access_key_id", ""),
            "secret_access_key": config.get("secret_access_key")
                or config.get("aws_secret_access_key", ""),
            "role_arn": config.get("role_arn", ""),
            "external_id": config.get("external_id", ""),
            "role_session_name": config.get(
                "role_session_name", "CostPilotAdvisor",
            ),
            "region": primary_region,
        }
        adapter = AWSAdapter(adapter_config)
        session = adapter._get_session()

        sts_client = session.client("sts", region_name=primary_region)
        try:
            account_id = sts_client.get_caller_identity().get("Account", "")
        except Exception as e:
            logger.warning("COH: STS get_caller_identity failed: %s", e)
            account_id = ""

        # Cost Optimization Hub is a regional service but returns
        # recommendations for all regions. us-east-1 is the canonical
        # endpoint.
        coh_client = session.client(
            "cost-optimization-hub", region_name="us-east-1",
        )

        findings: list[NormalizedAdvisorFinding] = []
        try:
            paginator = coh_client.get_paginator("list_recommendations")
            for page in paginator.paginate():
                for rec in page.get("items", []):
                    finding = self._normalize(rec, account_id)
                    if finding is not None:
                        findings.append(finding)
        except Exception as e:
            logger.warning(
                "Cost Optimization Hub: list_recommendations failed: %s", e,
            )

        logger.info(
            "Cost Optimization Hub ingest: %d recommendations for account %s",
            len(findings), account_id or "<unknown>",
        )
        return findings

    @staticmethod
    def _normalize(rec: dict[str, Any], account_id: str) -> NormalizedAdvisorFinding | None:
        """Convert a COH recommendation item to a normalized finding."""
        try:
            action_type = rec.get("actionType", "")
            finding_type = _ACTION_TYPE_TO_FINDING_TYPE.get(action_type)
            if not finding_type:
                # Unknown action type — still persist with a generic key
                finding_type = f"cost_optimization_hub.{action_type}"

            resource_id = rec.get("resourceId", "")
            resource_type = rec.get("resourceType", "")
            region = rec.get("region", "")

            estimated_saving = 0.0
            estimated_monthly = rec.get("estimatedMonthlySavings", {})
            if isinstance(estimated_monthly, dict):
                estimated_saving = float(estimated_monthly.get("value", 0) or 0)

            severity = _RESOURCE_TYPE_SEVERITY.get(resource_type, "medium")

            return NormalizedAdvisorFinding(
                cloud="aws_cnr",
                account_id=account_id,
                source_service="AWS Cost Optimization Hub",
                finding_type=finding_type,
                resource_id=resource_id,
                region=region,
                severity=severity,
                estimated_saving=estimated_saving,
                raw_payload={
                    "action_type": action_type,
                    "resource_type": resource_type,
                    "recommendation_id": rec.get("recommendationId", ""),
                    "source": rec.get("source", ""),
                    "estimated_monthly_savings": estimated_monthly,
                    "estimated_savings_percentage": rec.get(
                        "estimatedSavingsPercentage", 0,
                    ),
                    "current_resource_type": rec.get("currentResourceType", ""),
                    "recommended_resource_type": rec.get("recommendedResourceType", ""),
                },
            )
        except Exception as e:
            logger.debug("Failed to normalize COH recommendation: %s", e)
            return None
