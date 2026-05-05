"""AWS Compute Optimizer ingestor.

Step 3 of plans/rule-data-source-strategy.md.

Bulk API calls (one per resource family) return pre-scored
recommendations for the entire account. No per-resource CloudWatch
crawling required.

API surface:
    - get_ec2_instance_recommendations
    - get_ebs_volume_recommendations
    - get_lambda_function_recommendations

Each emits a `finding` enum
(Underprovisioned | Overprovisioned | Optimized | NotOptimized).
We normalize to the keys defined in
`app.advisor_findings.mapping.AWS_COMPUTE_OPTIMIZER_MAP`.

Required IAM (read-only):
    compute-optimizer:Get*
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.advisor_findings.ingestors.base import AdvisorIngestor
from app.advisor_findings.schemas import NormalizedAdvisorFinding

logger = logging.getLogger(__name__)


# Compute Optimizer is per-region. To cover a multi-region estate we
# discover the account's enabled regions via EC2 and call the API in
# each one in parallel. Customers can override via
# `config["advisor_regions"]` (explicit list) or
# `config["advisor_region_strategy"]` ("primary" | "all", default "all").
_DEFAULT_REGION = "us-east-1"

# Hard cap so a misconfigured account can't spawn 30+ threads and trip
# AWS account-wide STS / EC2 throttling. Most users have <10 active
# regions in practice.
_MAX_REGIONS = 16

# Severity heuristic: Underprovisioned is more urgent than Overprovisioned
_FINDING_SEVERITY: dict[str, str] = {
    "Underprovisioned": "high",
    "Overprovisioned": "medium",
    "NotOptimized": "medium",
    "Idle": "high",
}


class AwsComputeOptimizerIngestor(AdvisorIngestor):
    """Pulls recommendations from AWS Compute Optimizer."""

    source_service = "AWS Compute Optimizer"

    async def fetch(self, config: dict) -> list[NormalizedAdvisorFinding]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("AWS Compute Optimizer ingestion failed")
            return []

    # ---- sync helpers (run in a worker thread) -----------------------------

    def _fetch_sync(self, config: dict) -> list[NormalizedAdvisorFinding]:
        # Reuse the AWS adapter's session logic so assume-role accounts and
        # static-key accounts both work identically. The adapter's
        # `_get_session` transparently mints temporary credentials when
        # `role_arn` is set (see AWSAdapter docstring).
        from app.cloud_accounts.adapters.aws import AWSAdapter

        # The adapter's config key names (`access_key_id`, etc.) differ
        # from boto3's (`aws_access_key_id`). Accept both so this ingestor
        # can be driven directly from a stored CloudAccount.config JSON.
        primary_region = (
            config.get("region")
            or config.get("region_name")
            or _DEFAULT_REGION
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

        # Caller identity is region-agnostic; do it once.
        sts_client = session.client("sts", region_name=primary_region)
        try:
            account_id = sts_client.get_caller_identity().get("Account", "")
        except Exception as e:
            logger.warning("Compute Optimizer: STS get_caller_identity failed: %s", e)
            account_id = ""

        regions = self._resolve_regions(session, config, primary_region)
        logger.info(
            "Compute Optimizer ingest: scanning %d region(s) for account %s: %s",
            len(regions), account_id or "<unknown>", regions,
        )

        findings: list[NormalizedAdvisorFinding] = []
        # Fan out per-region in parallel — each region's calls run on a
        # worker thread and we merge the results. Per-region exceptions
        # are isolated by `_fetch_for_region` returning [].
        with ThreadPoolExecutor(max_workers=min(len(regions), 8)) as pool:
            futures = {
                pool.submit(self._fetch_for_region, session, region, account_id): region
                for region in regions
            }
            for fut in as_completed(futures):
                region = futures[fut]
                try:
                    findings.extend(fut.result())
                except Exception as e:
                    logger.warning(
                        "Compute Optimizer scan failed for region %s: %s",
                        region, e,
                    )

        logger.info(
            "Compute Optimizer ingest: %d findings for account %s across %d region(s)",
            len(findings), account_id or "<unknown>", len(regions),
        )
        return findings

    def _fetch_for_region(
        self, session: Any, region: str, account_id: str,
    ) -> list[NormalizedAdvisorFinding]:
        """Run all three resource-family scans for a single region."""
        co_client = session.client("compute-optimizer", region_name=region)
        out: list[NormalizedAdvisorFinding] = []
        out.extend(self._fetch_ec2(co_client, account_id, region))
        out.extend(self._fetch_ebs(co_client, account_id, region))
        out.extend(self._fetch_lambda(co_client, account_id, region))
        return out

    def _resolve_regions(
        self, session: Any, config: dict, primary_region: str,
    ) -> list[str]:
        """Decide which regions to scan.

        Resolution order (most specific wins):
            1. `config["advisor_regions"]` — explicit list, used as-is
               (still bounded by `_MAX_REGIONS`).
            2. `config["advisor_region_strategy"] == "primary"` — only
               the primary region.
            3. Otherwise discover via `ec2:DescribeRegions` (default).
            4. On any failure, fall back to `[primary_region]` so the
               scan still produces useful results.
        """
        explicit = config.get("advisor_regions")
        if explicit:
            return list(explicit)[:_MAX_REGIONS]

        strategy = (config.get("advisor_region_strategy") or "all").lower()
        if strategy == "primary":
            return [primary_region]

        try:
            ec2 = session.client("ec2", region_name=primary_region)
            resp = ec2.describe_regions(AllRegions=False)
            regions = [
                r["RegionName"]
                for r in resp.get("Regions", [])
                if r.get("OptInStatus") in (None, "opt-in-not-required", "opted-in")
            ]
            # Stable ordering: primary first, others alphabetically. This
            # keeps log output deterministic and makes the unique index
            # in `advisor_findings` consistent across re-runs.
            regions = sorted(set(regions))
            if primary_region in regions:
                regions = [primary_region] + [r for r in regions if r != primary_region]
            return regions[:_MAX_REGIONS] or [primary_region]
        except Exception as e:
            logger.warning(
                "Region discovery failed (%s); falling back to primary region %s",
                e, primary_region,
            )
            return [primary_region]

    def _fetch_ec2(
        self, client: Any, account_id: str, region: str = "",
    ) -> list[NormalizedAdvisorFinding]:
        out: list[NormalizedAdvisorFinding] = []
        try:
            paginator = client.get_paginator("get_ec2_instance_recommendations")
            for page in paginator.paginate():
                for rec in page.get("instanceRecommendations", []):
                    finding = rec.get("finding", "")
                    if finding == "Optimized":
                        continue
                    saving = self._extract_saving(rec.get("recommendationOptions", []))
                    arn = rec.get("instanceArn", "")
                    out.append(NormalizedAdvisorFinding(
                        cloud="aws_cnr",
                        account_id=account_id,
                        source_service=self.source_service,
                        finding_type=f"compute_optimizer.ec2.{finding}",
                        resource_id=arn,
                        region=region or self._region_from_arn(arn),
                        severity=_FINDING_SEVERITY.get(finding, "medium"),
                        estimated_saving=saving,
                        raw_payload={
                            "instance_name": rec.get("instanceName", ""),
                            "current_type": rec.get("currentInstanceType", ""),
                            "look_back_period": rec.get("lookBackPeriodInDays"),
                            "finding_reason_codes": rec.get("findingReasonCodes", []),
                        },
                    ))
        except Exception as e:
            logger.debug("Compute Optimizer EC2 fetch failed: %s", e)
        return out

    def _fetch_ebs(
        self, client: Any, account_id: str, region: str = "",
    ) -> list[NormalizedAdvisorFinding]:
        out: list[NormalizedAdvisorFinding] = []
        try:
            paginator = client.get_paginator("get_ebs_volume_recommendations")
            for page in paginator.paginate():
                for rec in page.get("volumeRecommendations", []):
                    finding = rec.get("finding", "")
                    if finding == "Optimized":
                        continue
                    saving = self._extract_saving(rec.get("volumeRecommendationOptions", []))
                    arn = rec.get("volumeArn", "")
                    out.append(NormalizedAdvisorFinding(
                        cloud="aws_cnr",
                        account_id=account_id,
                        source_service=self.source_service,
                        finding_type=f"compute_optimizer.ebs.{finding}",
                        resource_id=arn,
                        region=region or self._region_from_arn(arn),
                        severity=_FINDING_SEVERITY.get(finding, "medium"),
                        estimated_saving=saving,
                        raw_payload={
                            "current_configuration": rec.get("currentConfiguration", {}),
                            "utilization_metrics": rec.get("utilizationMetrics", []),
                        },
                    ))
        except Exception as e:
            logger.debug("Compute Optimizer EBS fetch failed: %s", e)
        return out

    def _fetch_lambda(
        self, client: Any, account_id: str, region: str = "",
    ) -> list[NormalizedAdvisorFinding]:
        out: list[NormalizedAdvisorFinding] = []
        try:
            paginator = client.get_paginator("get_lambda_function_recommendations")
            for page in paginator.paginate():
                for rec in page.get("lambdaFunctionRecommendations", []):
                    finding = rec.get("finding", "")
                    if finding == "Optimized":
                        continue
                    saving = self._extract_saving(
                        rec.get("memorySizeRecommendationOptions", [])
                    )
                    arn = rec.get("functionArn", "")
                    out.append(NormalizedAdvisorFinding(
                        cloud="aws_cnr",
                        account_id=account_id,
                        source_service=self.source_service,
                        finding_type=f"compute_optimizer.lambda.{finding}",
                        resource_id=arn,
                        region=region or self._region_from_arn(arn),
                        severity=_FINDING_SEVERITY.get(finding, "medium"),
                        estimated_saving=saving,
                        raw_payload={
                            "current_memory_size": rec.get("currentMemorySize"),
                            "number_of_invocations": rec.get("numberOfInvocations"),
                            "finding_reason_codes": rec.get("findingReasonCodes", []),
                        },
                    ))
        except Exception as e:
            logger.debug("Compute Optimizer Lambda fetch failed: %s", e)
        return out

    @staticmethod
    def _extract_saving(options: list[dict]) -> float:
        """Pull the best estimated monthly saving from a recommendationOptions list.

        Compute Optimizer returns one or more options ranked by performance
        risk. We take the option with the largest savings-opportunity dollar
        value (caller decides whether to surface).
        """
        best = 0.0
        for opt in options:
            so = opt.get("savingsOpportunity") or {}
            est = so.get("estimatedMonthlySavings") or {}
            try:
                value = float(est.get("value", 0) or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value > best:
                best = value
        return best

    @staticmethod
    def _region_from_arn(arn: str) -> str:
        """ARN format: arn:aws:<svc>:<region>:<account>:<resource>"""
        if not arn:
            return ""
        parts = arn.split(":")
        return parts[3] if len(parts) >= 4 else ""
