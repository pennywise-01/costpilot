"""IAM policy registry for cloud-account onboarding.

Centralizes the read-only actions CostPilot needs per cloud and per
data-source tier. Used by:
    - Onboarding UI (download / copy policy JSON)
    - `GET /api/v1/cloud-accounts/iam-policy`
    - Documentation generators

Kept as data (lists of strings) — not hand-rolled JSON — so tests can
diff the flat action list and we can machine-verify that the actions
an ingestor calls are actually granted by the published policy.

Tiers match `app.recommendation_rules.builtin_rules.DATA_SOURCE_*`:
    - billing: cost/usage export + basic resource describe
    - advisor: provider advisor / recommender APIs
    - config:  resource state + IAM + security graph (Tier-2, not yet
               wired to ingestors; included here so docs are accurate)
"""

from __future__ import annotations

from typing import Iterable

from app.shared.enums import CloudType

# ---------------------------------------------------------------------------
# AWS
# ---------------------------------------------------------------------------

AWS_BILLING_ACTIONS: list[str] = [
    "ce:GetCostAndUsage",
    "ce:GetCostForecast",
    "ec2:DescribeInstances",
    "ec2:DescribeRegions",
    "ec2:DescribeVolumes",
    "rds:DescribeDBInstances",
    "lambda:ListFunctions",
    "s3:ListAllMyBuckets",
    "sts:GetCallerIdentity",
]

# Compute Optimizer, Trusted Advisor (requires Business/Enterprise support),
# and Cost Optimization Hub are all read-only advisor APIs.
AWS_ADVISOR_ACTIONS: list[str] = [
    "compute-optimizer:GetEC2InstanceRecommendations",
    "compute-optimizer:GetEBSVolumeRecommendations",
    "compute-optimizer:GetLambdaFunctionRecommendations",
    "compute-optimizer:GetAutoScalingGroupRecommendations",
    "compute-optimizer:GetRecommendationSummaries",
    "compute-optimizer:GetEnrollmentStatus",
    "support:DescribeTrustedAdvisorChecks",
    "support:DescribeTrustedAdvisorCheckResult",
    "support:DescribeTrustedAdvisorCheckSummaries",
    "cost-optimization-hub:ListRecommendations",
    "cost-optimization-hub:GetRecommendation",
]

# Resource state / IAM / security graph — Tier-2, not yet wired to an
# ingestor. Kept here so the published policy is complete and forward-
# compatible; users don't have to re-edit IAM when we flip Tier-2 on.
AWS_CONFIG_ACTIONS: list[str] = [
    "config:DescribeConfigRules",
    "config:SelectResourceConfig",
    "config:SelectAggregateResourceConfig",
    "iam:ListUsers",
    "iam:ListAccessKeys",
    "iam:ListMFADevices",
    "iam:GetAccountPasswordPolicy",
    "iam:GenerateCredentialReport",
    "iam:GetCredentialReport",
    "ec2:DescribeSecurityGroups",
    "ec2:DescribeNetworkInterfaces",
    "s3:GetBucketPolicyStatus",
    "s3:GetBucketPublicAccessBlock",
    "s3:GetBucketEncryption",
    "rds:DescribeDBSnapshots",
    "ebs:ListSnapshots",
]


# ---------------------------------------------------------------------------
# Azure — role assignments rather than individual action lists. We map
# each tier to the names of the built-in Azure roles users should grant
# to CostPilot's service principal.
# ---------------------------------------------------------------------------

AZURE_ROLES_BY_TIER: dict[str, list[str]] = {
    "billing": ["Cost Management Reader", "Reader"],
    "advisor": ["Reader"],  # covers Microsoft.Advisor/recommendations/read
    "config":  ["Reader", "Security Reader"],
}


# ---------------------------------------------------------------------------
# GCP — predefined IAM roles per tier. `roles/recommender.viewer` alone
# doesn't grant visibility into every sub-recommender, so we enumerate.
# ---------------------------------------------------------------------------

GCP_ROLES_BY_TIER: dict[str, list[str]] = {
    "billing": [
        "roles/billing.viewer",
        "roles/bigquery.dataViewer",     # for BigQuery-exported billing
        "roles/bigquery.jobUser",
    ],
    "advisor": [
        "roles/recommender.viewer",
        "roles/recommender.computeViewer",
        "roles/recommender.iamViewer",
    ],
    "config": [
        "roles/cloudasset.viewer",
        "roles/iam.securityReviewer",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

VALID_TIERS: set[str] = {"billing", "advisor", "config"}


def _aws_actions_for_tiers(tiers: Iterable[str]) -> list[str]:
    """Union of AWS actions for the requested tiers, deduplicated and sorted."""
    buckets = {
        "billing": AWS_BILLING_ACTIONS,
        "advisor": AWS_ADVISOR_ACTIONS,
        "config":  AWS_CONFIG_ACTIONS,
    }
    seen: set[str] = set()
    for tier in tiers:
        for action in buckets.get(tier, []):
            seen.add(action)
    return sorted(seen)


def build_aws_policy_document(
    tiers: Iterable[str],
    trust_principal: str | None = None,
    external_id: str | None = None,
) -> dict:
    """Return an AWS IAM policy document (inline policy JSON).

    Args:
        tiers: subset of {"billing", "advisor", "config"}
        trust_principal: if supplied, the returned dict also includes a
            `TrustPolicy` key holding an `sts:AssumeRole` trust policy
            for that principal (CostPilot's AWS account ARN).
        external_id: external-id required on the trust policy.
    """
    actions = _aws_actions_for_tiers(tiers)
    policy: dict = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CostPilotReadOnly",
                "Effect": "Allow",
                "Action": actions,
                "Resource": "*",
            }
        ],
    }
    if trust_principal:
        trust: dict = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": trust_principal},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
        if external_id:
            trust["Statement"][0]["Condition"] = {
                "StringEquals": {"sts:ExternalId": external_id}
            }
        return {"Policy": policy, "TrustPolicy": trust}
    return policy


def build_policy(
    cloud: CloudType | str,
    tiers: Iterable[str],
    trust_principal: str | None = None,
    external_id: str | None = None,
) -> dict:
    """Cloud-dispatching entry point used by the HTTP endpoint."""
    ctype = cloud if isinstance(cloud, CloudType) else _coerce_cloud(cloud)
    tier_list = _validate_tiers(tiers)

    if ctype in (CloudType.AWS,):
        return build_aws_policy_document(
            tier_list, trust_principal=trust_principal, external_id=external_id,
        )
    if ctype in (CloudType.AZURE, CloudType.AZURE_TENANT):
        return {
            "cloud": "azure",
            "roles": _dedupe([
                r for t in tier_list for r in AZURE_ROLES_BY_TIER.get(t, [])
            ]),
            "instructions": (
                "Assign these built-in Azure roles to the CostPilot service "
                "principal at the subscription scope (or root management "
                "group scope for multi-subscription tenants)."
            ),
        }
    if ctype in (CloudType.GCP, CloudType.GCP_TENANT):
        return {
            "cloud": "gcp",
            "roles": _dedupe([
                r for t in tier_list for r in GCP_ROLES_BY_TIER.get(t, [])
            ]),
            "instructions": (
                "Grant these predefined roles to the CostPilot service "
                "account on the target project (or organization for "
                "multi-project estates)."
            ),
        }
    raise ValueError(f"Unsupported cloud type for IAM policy: {cloud!r}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_cloud(cloud: str) -> CloudType:
    try:
        return CloudType(cloud)
    except ValueError:
        # accept friendly aliases
        aliases = {
            "aws": CloudType.AWS,
            "azure": CloudType.AZURE,
            "gcp": CloudType.GCP,
        }
        key = cloud.lower()
        if key in aliases:
            return aliases[key]
        raise ValueError(f"Unknown cloud: {cloud!r}")


def _validate_tiers(tiers: Iterable[str]) -> list[str]:
    out = [t for t in tiers if t in VALID_TIERS]
    if not out:
        raise ValueError(
            f"At least one tier from {sorted(VALID_TIERS)} is required"
        )
    return out


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
