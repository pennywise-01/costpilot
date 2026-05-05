"""Mapping from advisor finding types to built-in recommendation rule IDs.

Step 4 of plans/rule-data-source-strategy.md. The mapping is intentionally
data-only (a Python dict, not a DB table) — it changes when we ship support
for a new finding type, which is a code release anyway.

Finding type keys are namespaced by source service to avoid collisions
between providers (e.g. AWS Compute Optimizer's "Underprovisioned" overlaps
with the GCP Recommender's IDLE_INSTANCE in concept but not in payload).

Built-in rule IDs follow the convention `builtin-NNN` defined in
`app/recommendation_rules/builtin_rules.py`.
"""

from app.recommendation_rules.builtin_rules import BUILTIN_RULE_ID_PREFIX


def builtin_id(seq: int) -> str:
    """Format a built-in rule sequence number into its full ID."""
    return f"{BUILTIN_RULE_ID_PREFIX}{seq:03d}"


# ---------------------------------------------------------------------------
# AWS Compute Optimizer
# ---------------------------------------------------------------------------
# Compute Optimizer returns a `finding` enum on each recommendation:
#   EC2 instance:  Underprovisioned | Overprovisioned | Optimized | NotOptimized
#   EBS volume:    NotOptimized     | Optimized
#   Lambda:        Underprovisioned | Overprovisioned | NotOptimized | Optimized
# We surface only the actionable ones; "Optimized" is intentionally excluded.

AWS_COMPUTE_OPTIMIZER_MAP: dict[str, str] = {
    # EC2 right-sizing
    "compute_optimizer.ec2.Underprovisioned": builtin_id(25),  # Scale up saturated instances
    "compute_optimizer.ec2.Overprovisioned":  builtin_id(4),   # Right-size over-provisioned
    "compute_optimizer.ec2.NotOptimized":     builtin_id(4),
    # EBS — Compute Optimizer flags volumes that are over-provisioned for IOPS
    "compute_optimizer.ebs.NotOptimized":     builtin_id(31),  # Match storage tier to IOPS
    # Lambda
    "compute_optimizer.lambda.Underprovisioned": builtin_id(25),
    "compute_optimizer.lambda.Overprovisioned":  builtin_id(4),
    "compute_optimizer.lambda.NotOptimized":     builtin_id(4),
    # Idle instances are surfaced as low-utilization findings
    "compute_optimizer.ec2.Idle":             builtin_id(1),   # Terminate idle compute
}

# ---------------------------------------------------------------------------
# AWS Trusted Advisor
# ---------------------------------------------------------------------------
AWS_TRUSTED_ADVISOR_MAP: dict[str, str] = {
    # Cost
    "trusted_advisor.LowUtilizationEC2":              builtin_id(1),
    "trusted_advisor.IdleLoadBalancers":              builtin_id(6),
    "trusted_advisor.UnassociatedElasticIPAddresses": builtin_id(7),
    "trusted_advisor.UnderutilizedEBSVolumes":        builtin_id(31),
    # Security
    "trusted_advisor.IAMAccessKeyRotation":           builtin_id(12),
    "trusted_advisor.MFAOnRootAccount":               builtin_id(14),
    "trusted_advisor.S3BucketPermissions":            builtin_id(9),
    "trusted_advisor.SecurityGroupsSpecificPortsUnrestricted": builtin_id(16),
}

# ---------------------------------------------------------------------------
# AWS Cost Optimization Hub
# ---------------------------------------------------------------------------
AWS_COST_OPTIMIZATION_HUB_MAP: dict[str, str] = {
    "cost_optimization_hub.RightSize":                    builtin_id(4),
    "cost_optimization_hub.Stop":                         builtin_id(1),
    "cost_optimization_hub.Upgrade":                      builtin_id(25),
    "cost_optimization_hub.PurchaseReservedInstances":     builtin_id(5),
    "cost_optimization_hub.PurchaseSavingsPlans":          builtin_id(5),
    "cost_optimization_hub.MigrateToGraviton":             builtin_id(25),
    "cost_optimization_hub.Delete":                        builtin_id(1),
}

# ---------------------------------------------------------------------------
# Azure Advisor
# ---------------------------------------------------------------------------
AZURE_ADVISOR_MAP: dict[str, str] = {
    "azure_advisor.Cost.IdleVirtualMachines":      builtin_id(1),
    "azure_advisor.Cost.RightSizeVirtualMachines": builtin_id(4),
    "azure_advisor.Cost.ReservedInstance":         builtin_id(5),
    "azure_advisor.Cost.IdleLoadBalancers":        builtin_id(6),
    "azure_advisor.Cost.UnassociatedPublicIP":     builtin_id(7),
    "azure_advisor.Security.MFAEnabled":           builtin_id(14),
}

# ---------------------------------------------------------------------------
# GCP Recommender
# ---------------------------------------------------------------------------
GCP_RECOMMENDER_MAP: dict[str, str] = {
    "gcp_recommender.google.compute.instance.IdleResourceRecommender":    builtin_id(1),
    "gcp_recommender.google.compute.instance.MachineTypeRecommender":     builtin_id(4),
    "gcp_recommender.google.compute.commitment.UsageCommitmentRecommender": builtin_id(5),
    "gcp_recommender.google.compute.address.IdleResourceRecommender":     builtin_id(7),
    "gcp_recommender.google.iam.policy.Recommender":                      builtin_id(13),
}


# Aggregated, lookup-by-key dispatch table. Importing modules use this as
# the single source of truth.
ADVISOR_FINDING_TO_BUILTIN_RULE: dict[str, str] = {
    **AWS_COMPUTE_OPTIMIZER_MAP,
    **AWS_TRUSTED_ADVISOR_MAP,
    **AWS_COST_OPTIMIZATION_HUB_MAP,
    **AZURE_ADVISOR_MAP,
    **GCP_RECOMMENDER_MAP,
}


def resolve_builtin_rule_id(finding_type: str) -> str | None:
    """Resolve an advisor finding_type string to its built-in rule ID.

    Returns None when the finding type isn't yet mapped (the finding is
    still persisted; it's just not driving any rule). This lets us ingest
    safely ahead of mapping coverage.
    """
    return ADVISOR_FINDING_TO_BUILTIN_RULE.get(finding_type)
