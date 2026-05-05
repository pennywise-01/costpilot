"""AWS Trusted Advisor ingestor.

Pulls findings from AWS Trusted Advisor (`support:DescribeTrustedAdvisorChecks`
+ `support:DescribeTrustedAdvisorCheckResult`). Trusted Advisor pre-scores
resources across Cost, Security, Fault Tolerance, Performance, and Service
Quotas — we ingest the flagged resources and map them to built-in rules via
`app.advisor_findings.mapping.AWS_TRUSTED_ADVISOR_MAP`.

Requires Business or Enterprise support plan on the AWS account.

Required IAM (read-only):
    support:DescribeTrustedAdvisorChecks
    support:DescribeTrustedAdvisorCheckResult
    support:DescribeTrustedAdvisorCheckSummaries
"""

import asyncio
import logging
from typing import Any

from app.advisor_findings.ingestors.base import AdvisorIngestor
from app.advisor_findings.schemas import NormalizedAdvisorFinding

logger = logging.getLogger(__name__)

# Trusted Advisor check IDs → our namespaced finding_type keys.
# Only checks that map to built-in rules are included.
_CHECK_ID_TO_FINDING_TYPE: dict[str, str] = {
    # Cost
    "Qch7DwouX1": "trusted_advisor.LowUtilizationEC2",
    "DAvU99Dc4C": "trusted_advisor.IdleLoadBalancers",
    "Z4AUBRNSmz": "trusted_advisor.UnassociatedElasticIPAddresses",
    "hjLMh88uMj": "trusted_advisor.UnderutilizedEBSVolumes",
    # Security
    "Yw2Q7Prv1J": "trusted_advisor.IAMAccessKeyRotation",
    "12Fnkpl8Y5": "trusted_advisor.MFAOnRootAccount",
    "Pfx4R2qGli": "trusted_advisor.S3BucketPermissions",
    "HCP4007jGY": "trusted_advisor.SecurityGroupsSpecificPortsUnrestricted",
}

# Severity heuristic based on Trusted Advisor category
_CATEGORY_SEVERITY: dict[str, str] = {
    "cost_optimizing": "medium",
    "security": "high",
    "fault_tolerance": "high",
    "performance": "medium",
    "service_limits": "low",
}


class AwsTrustedAdvisorIngestor(AdvisorIngestor):
    """Pulls findings from AWS Trusted Advisor."""

    source_service = "AWS Trusted Advisor"

    async def fetch(self, config: dict) -> list[NormalizedAdvisorFinding]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("AWS Trusted Advisor ingestion failed")
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
            logger.warning("Trusted Advisor: STS get_caller_identity failed: %s", e)
            account_id = ""

        # Support API is only available in us-east-1 (global) or
        # ap-southeast-1 / eu-west-1 for certain endpoints.
        support_client = session.client("support", region_name="us-east-1")

        findings: list[NormalizedAdvisorFinding] = []
        try:
            # Get all available checks
            checks_resp = support_client.describe_trusted_advisor_checks(
                language="en",
            )
            checks = checks_resp.get("checks", [])

            for check in checks:
                check_id = check.get("id", "")
                finding_type = _CHECK_ID_TO_FINDING_TYPE.get(check_id)
                if not finding_type:
                    continue  # Skip checks we haven't mapped

                category = check.get("category", "")
                severity = _CATEGORY_SEVERITY.get(category, "medium")

                try:
                    result = support_client.describe_trusted_advisor_check_result(
                        checkId=check_id,
                        language="en",
                    )
                    check_result = result.get("result", {})
                    flagged_resources = check_result.get("flaggedResources", [])

                    for resource in flagged_resources:
                        resource_id = resource.get("resourceId", "")
                        metadata = resource.get("metadata", []) or []

                        # Extract region from metadata if available
                        region = ""
                        if len(metadata) > 2:
                            region = str(metadata[2]) if metadata[2] else ""

                        # Extract estimated savings if present
                        estimated_saving = 0.0
                        status = resource.get("status", "")
                        if len(metadata) > 4 and metadata[4]:
                            try:
                                estimated_saving = float(str(metadata[4]).replace("$", "").replace(",", ""))
                            except (TypeError, ValueError):
                                estimated_saving = 0.0

                        findings.append(NormalizedAdvisorFinding(
                            cloud="aws_cnr",
                            account_id=account_id,
                            source_service=self.source_service,
                            finding_type=finding_type,
                            resource_id=resource_id,
                            region=region,
                            severity=severity,
                            estimated_saving=estimated_saving,
                            raw_payload={
                                "check_id": check_id,
                                "check_name": check.get("name", ""),
                                "category": category,
                                "status": status,
                                "metadata": [
                                    str(m) for m in metadata
                                    if not any(kw in str(m).lower() for kw in ("key", "secret", "token"))
                                ],
                            },
                        ))
                except Exception as e:
                    logger.debug(
                        "Trusted Advisor: check %s failed: %s",
                        check_id, e,
                    )
        except Exception as e:
            logger.warning(
                "Trusted Advisor: describe_trusted_advisor_checks failed: %s", e,
            )

        logger.info(
            "Trusted Advisor ingest: %d findings for account %s",
            len(findings), account_id or "<unknown>",
        )
        return findings
