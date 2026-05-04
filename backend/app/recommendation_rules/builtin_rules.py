"""Built-in recommendation rules derived from the Well-Architected Framework
(AWS, Azure, GCP). These rules are cross-cloud (not CSP-specific), read-only,
and surfaced alongside user-created rules on the Recommendation Rules page.

Covers five pillars: Cost, Security, Reliability, Performance,
Operational Excellence (8 rules per pillar, 40 total).
"""
from datetime import datetime, timezone

from app.recommendation_rules.schemas import RecRuleResponse
from app.shared.enums import RecommendationSeverity, SavingType


BUILTIN_RULE_ID_PREFIX = "builtin-"

# Frozen timestamp so responses are stable across requests.
_BUILTIN_CREATED_AT = datetime(2024, 1, 1, tzinfo=timezone.utc)

# Data sources the rule needs to actually evaluate findings.
#   "billing" - derivable from BigQuery / CUR / Cost Mgmt billing exports.
#   "metrics" - needs utilization telemetry (CloudWatch / Azure Monitor /
#               Cloud Monitoring).
#   "config"  - needs resource state / IAM / security APIs (Config, Resource
#               Graph, Asset Inventory, IAM, security groups).
DATA_SOURCE_BILLING = "billing"
DATA_SOURCE_METRICS = "metrics"
DATA_SOURCE_CONFIG = "config"

# Data sources currently wired up. Update when new ingestors ship.
AVAILABLE_DATA_SOURCES: set[str] = {DATA_SOURCE_BILLING}


def _rule(
    seq: int,
    name: str,
    category: str,
    severity: RecommendationSeverity,
    description: str,
    action: str,
    saving_type: SavingType = SavingType.FIXED,
    saving_value: float = 0.0,
    data_source: str = DATA_SOURCE_BILLING,
) -> dict:
    return {
        "id": f"{BUILTIN_RULE_ID_PREFIX}{seq:03d}",
        "name": name,
        "description": description,
        "priority": seq,
        "organization_id": "",
        "creator_id": "",
        "active": True,
        "category": category,
        "severity": severity,
        "action_description": action,
        "saving_type": saving_type,
        "saving_value": saving_value,
        "conditions": [],
        "created_at": _BUILTIN_CREATED_AT,
        "is_builtin": True,
        "data_source": data_source,
    }


# ---------------------------------------------------------------------------
# Cost Optimization (Well-Architected: AWS Cost Optimization / Azure Cost
# Optimization / GCP Cost Optimization pillar)
# ---------------------------------------------------------------------------
_COST_RULES: list[dict] = [
    _rule(
        1,
        "Terminate idle compute instances",
        "cost",
        RecommendationSeverity.HIGH,
        "Flag VMs / EC2 / Compute Engine instances with <5% average CPU and <5MB/s network over 14 days. Idle compute is the single largest source of waste in most cloud estates.",
        "Stop or terminate consistently idle instances after confirming with the workload owner. Snapshot critical disks before deletion.",
        SavingType.PERCENTAGE,
        100,
        data_source=DATA_SOURCE_METRICS,
    ),
    _rule(
        2,
        "Delete unattached block storage volumes",
        "cost",
        RecommendationSeverity.MEDIUM,
        "Block storage volumes (EBS, Azure Managed Disks, GCP Persistent Disks) in the 'available/unattached' state accumulate charges with no workload benefit.",
        "Snapshot for retention if needed, then delete volumes unattached for more than 14 days.",
        SavingType.PERCENTAGE,
        100,
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        3,
        "Remove orphaned snapshots and images",
        "cost",
        RecommendationSeverity.LOW,
        "Snapshots whose source volume or AMI/image no longer exists rarely provide value but continue to accrue storage cost.",
        "Apply a lifecycle policy that deletes orphaned snapshots older than the retention window (e.g. 90 days).",
        SavingType.PERCENTAGE,
        100,
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        4,
        "Right-size over-provisioned instances",
        "cost",
        RecommendationSeverity.HIGH,
        "Instances whose peak CPU and memory usage stays below 40% for 14+ days are candidates for downsizing one or two families.",
        "Use the cloud-native rightsizing recommender or load tests to move workloads to a smaller SKU.",
        SavingType.PERCENTAGE,
        40,
        data_source=DATA_SOURCE_METRICS,
    ),
    _rule(
        5,
        "Commit to Reserved Instances or Savings Plans for steady workloads",
        "cost",
        RecommendationSeverity.HIGH,
        "Workloads with >80% uptime for 60+ days cost significantly less under 1- or 3-year commitments (Reserved Instances, Savings Plans, Committed Use Discounts).",
        "Analyze on-demand usage and purchase commitments sized to the stable baseline.",
        SavingType.PERCENTAGE,
        40,
        data_source=DATA_SOURCE_BILLING,
    ),
    _rule(
        6,
        "Delete unused load balancers",
        "cost",
        RecommendationSeverity.MEDIUM,
        "Load balancers with zero healthy backends or <1 request/minute for 7 days are likely remnants of decommissioned workloads.",
        "Remove load balancers with no active targets and no traffic for 7+ days.",
        SavingType.PERCENTAGE,
        100,
        data_source=DATA_SOURCE_METRICS,
    ),
    _rule(
        7,
        "Release unused public / static IP addresses",
        "cost",
        RecommendationSeverity.LOW,
        "Reserved public IPs (EIPs, Azure Public IPs, GCP static IPs) not attached to a running resource are billed hourly.",
        "Release public IPs that have been unattached for more than 48 hours.",
        SavingType.PERCENTAGE,
        100,
        data_source=DATA_SOURCE_BILLING,
    ),
    _rule(
        8,
        "Schedule non-production workloads to shut down after hours",
        "cost",
        RecommendationSeverity.HIGH,
        "Dev, test, and staging environments rarely need to run 24/7. Automating nightly and weekend shutdowns typically removes ~65% of their runtime.",
        "Apply instance schedules (EventBridge, Azure Automation, GCP instance schedules) to non-production resources.",
        SavingType.PERCENTAGE,
        65,
        data_source=DATA_SOURCE_BILLING,
    ),
]

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
_SECURITY_RULES: list[dict] = [
    _rule(
        9,
        "Block publicly accessible object storage buckets",
        "security",
        RecommendationSeverity.CRITICAL,
        "S3 buckets, Azure Blob containers, or GCS buckets configured for public read/write are a top cause of data exposure incidents.",
        "Enable account-level public access block. Require explicit exception approval for any public bucket.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        10,
        "Enforce encryption at rest for managed storage",
        "security",
        RecommendationSeverity.HIGH,
        "All block storage, object storage, and managed databases should use provider-managed or customer-managed keys for at-rest encryption.",
        "Enable default encryption on storage services. Use CMK/KMS keys for sensitive workloads.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        11,
        "Enforce TLS 1.2+ for data in transit",
        "security",
        RecommendationSeverity.HIGH,
        "Load balancers, API gateways, and managed databases should reject TLS versions below 1.2 and prefer strong cipher suites.",
        "Set minimum TLS policy to 1.2 or higher on public endpoints and deprecate weak ciphers.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        12,
        "Rotate IAM access keys and service-account keys every 90 days",
        "security",
        RecommendationSeverity.HIGH,
        "Long-lived access keys dramatically increase blast radius when leaked. Rotation enforces hygiene and invalidates stale credentials.",
        "Rotate user access keys and service account keys older than 90 days; prefer short-lived federated credentials.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        13,
        "Eliminate wildcard permissions on IAM roles and policies",
        "security",
        RecommendationSeverity.CRITICAL,
        "Policies containing action '*' on resource '*' violate the principle of least privilege and give attackers broad lateral movement if compromised.",
        "Scope policies to the minimum actions and resources required. Use IAM Access Analyzer / Azure PIM to identify unused permissions.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        14,
        "Require multi-factor authentication for privileged users",
        "security",
        RecommendationSeverity.CRITICAL,
        "Accounts with administrative or billing permissions that lack MFA are a primary target for credential-stuffing and phishing attacks.",
        "Enforce conditional access / organization-wide MFA policy for all privileged principals, especially root/owner accounts.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        15,
        "Remove inactive IAM users and service accounts",
        "security",
        RecommendationSeverity.MEDIUM,
        "Identities with no sign-in or API activity in the last 90 days expand the attack surface without providing business value.",
        "Disable or delete users and service accounts inactive for 90+ days after owner confirmation.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        16,
        "Restrict security groups and NSGs from 0.0.0.0/0 on admin ports",
        "security",
        RecommendationSeverity.CRITICAL,
        "Inbound rules that expose SSH (22), RDP (3389), or database ports to the internet are a leading vector for brute-force compromise.",
        "Restrict admin ports to bastion / VPN CIDRs. Use SSM Session Manager, Bastion, or IAP tunneling for remote access.",
        data_source=DATA_SOURCE_CONFIG,
    ),
]

# ---------------------------------------------------------------------------
# Reliability
# ---------------------------------------------------------------------------
_RELIABILITY_RULES: list[dict] = [
    _rule(
        17,
        "Deploy production databases with multi-AZ / zone redundancy",
        "reliability",
        RecommendationSeverity.HIGH,
        "Single-AZ managed databases cannot survive an availability-zone outage. Zone redundancy is the baseline Well-Architected reliability control.",
        "Enable Multi-AZ (RDS/Aurora), Zone-Redundant (Azure SQL/PostgreSQL), or regional HA (Cloud SQL) on production databases.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        18,
        "Enable automated backups with periodic restore tests",
        "reliability",
        RecommendationSeverity.HIGH,
        "Backups without a verified restore procedure provide false confidence. Regular restore rehearsals ensure RPO/RTO objectives are achievable.",
        "Enable automated backups on all stateful services and schedule quarterly restore drills.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        19,
        "Maintain at least two healthy instances behind every load balancer",
        "reliability",
        RecommendationSeverity.HIGH,
        "Single-instance back ends behind a load balancer offer no fault tolerance and defeat the purpose of the balancer.",
        "Set minimum desired capacity to 2 across multiple availability zones for production target groups.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        20,
        "Avoid single-AZ production workloads",
        "reliability",
        RecommendationSeverity.MEDIUM,
        "Auto-scaling groups, managed kubernetes node pools, and instance groups deployed in a single AZ are vulnerable to zone-scoped incidents.",
        "Span auto-scaling groups / node pools across 2+ availability zones in production.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        21,
        "Enable cross-region replication for critical object storage",
        "reliability",
        RecommendationSeverity.MEDIUM,
        "Business-critical buckets and blob containers should survive a regional outage via replication to a secondary region.",
        "Enable cross-region / geo-redundant replication for data classified as critical.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        22,
        "Configure health checks on all load balancer targets",
        "reliability",
        RecommendationSeverity.MEDIUM,
        "Without application-layer health checks, the load balancer may keep routing traffic to crashed processes, causing partial outages.",
        "Configure HTTP/HTTPS health checks hitting an app-level readiness endpoint for every target group.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        23,
        "Enable point-in-time recovery on production databases",
        "reliability",
        RecommendationSeverity.HIGH,
        "Daily backups alone can lose up to 24 hours of data. Point-in-time recovery bounds RPO to minutes for transactional stores.",
        "Enable PITR / continuous backup on production SQL, NoSQL, and managed caches.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        24,
        "Alert when service quotas exceed 80% consumption",
        "reliability",
        RecommendationSeverity.MEDIUM,
        "Silently hitting a quota (vCPUs, public IPs, API throughput) causes abrupt, hard-to-diagnose outages during traffic spikes or failover.",
        "Monitor quota usage and open proactive limit-increase tickets when any quota crosses 80%.",
        data_source=DATA_SOURCE_CONFIG,
    ),
]

# ---------------------------------------------------------------------------
# Performance Efficiency
# ---------------------------------------------------------------------------
_PERFORMANCE_RULES: list[dict] = [
    _rule(
        25,
        "Scale up instances saturated above 90% CPU",
        "performance",
        RecommendationSeverity.HIGH,
        "Instances running with sustained CPU above 90% for 1+ hour daily are throttling workloads and degrade p99 latency.",
        "Scale up the instance family or scale out horizontally to keep peak CPU below 80%.",
        data_source=DATA_SOURCE_METRICS,
    ),
    _rule(
        26,
        "Migrate workloads to the latest-generation instance family",
        "performance",
        RecommendationSeverity.MEDIUM,
        "Each new instance generation delivers 10-40% better price-performance. Legacy families (e.g. m4, Dv2) are both slower and more expensive per vCPU.",
        "Benchmark and migrate from last-generation families (m4, Dv2, n1) to current generations (m6/m7, Dv5, n2).",
        SavingType.PERCENTAGE,
        20,
        data_source=DATA_SOURCE_BILLING,
    ),
    _rule(
        27,
        "Front static public assets with a CDN",
        "performance",
        RecommendationSeverity.MEDIUM,
        "Serving static assets directly from origin incurs higher latency and egress cost. CDNs (CloudFront, Azure Front Door, Cloud CDN) cache at edge.",
        "Route static assets (JS/CSS/images/video) through a CDN with appropriate cache headers.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        28,
        "Add read replicas to databases with read-heavy load",
        "performance",
        RecommendationSeverity.MEDIUM,
        "Databases with >70% CPU whose workload is >80% reads can offload traffic to read replicas, improving latency and primary stability.",
        "Provision read replicas and route analytical / read-mostly queries to them.",
        data_source=DATA_SOURCE_METRICS,
    ),
    _rule(
        29,
        "Detect network-bandwidth-constrained instances",
        "performance",
        RecommendationSeverity.MEDIUM,
        "When instance egress is near the published NIC cap, packet-drop and tail latency spike. The instance family, not the application, is the bottleneck.",
        "Upgrade to instance families with higher networking performance or enable placement groups.",
        data_source=DATA_SOURCE_METRICS,
    ),
    _rule(
        30,
        "Enable enhanced / accelerated networking where supported",
        "performance",
        RecommendationSeverity.LOW,
        "ENA, SR-IOV, and accelerated networking reduce jitter and improve PPS for no additional cost on supported SKUs.",
        "Verify and enable enhanced networking on all eligible instances.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        31,
        "Match database storage tier to required IOPS",
        "performance",
        RecommendationSeverity.MEDIUM,
        "Databases running on burst-based storage (gp2, Standard HDD) whose credit balance routinely hits zero experience steep I/O throttling.",
        "Upgrade to provisioned-IOPS (io2, Premium SSD, Hyperdisk) when baseline IOPS consistently exceeds the burst budget.",
        data_source=DATA_SOURCE_METRICS,
    ),
    _rule(
        32,
        "Introduce an in-memory cache for hot read paths",
        "performance",
        RecommendationSeverity.MEDIUM,
        "Endpoints whose top queries repeat on small key sets benefit from a managed Redis / Memcached tier, cutting DB load and tail latency.",
        "Add a managed cache (ElastiCache, Azure Cache for Redis, Memorystore) in front of hot read paths.",
        data_source=DATA_SOURCE_METRICS,
    ),
]

# ---------------------------------------------------------------------------
# Operational Excellence
# ---------------------------------------------------------------------------
_OPS_RULES: list[dict] = [
    _rule(
        33,
        "Enforce a mandatory tagging policy on billable resources",
        "operational_excellence",
        RecommendationSeverity.HIGH,
        "Untagged resources break cost allocation, ownership tracking, and automated lifecycle management. Owner, environment, and cost-center are the baseline.",
        "Enforce tag policies / Azure Policy / GCP label constraints requiring owner, env, and cost-center tags on all billable resources.",
        data_source=DATA_SOURCE_BILLING,
    ),
    _rule(
        34,
        "Enforce consistent resource naming conventions",
        "operational_excellence",
        RecommendationSeverity.LOW,
        "Ad-hoc resource names make automation, dashboards, and incident response materially harder. A convention such as <env>-<service>-<role>-<n> scales.",
        "Document a naming convention and enforce it via policy, CI checks, or IaC linting.",
        data_source=DATA_SOURCE_BILLING,
    ),
    _rule(
        35,
        "Enable access and audit logging on public-facing services",
        "operational_excellence",
        RecommendationSeverity.HIGH,
        "Load balancers, API gateways, and storage buckets without access logs leave forensic and debugging gaps.",
        "Enable access logs on ALBs, CloudFront/Front Door/Cloud CDN, and object storage in front of users.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        36,
        "Centralize logs and metrics in a single observability platform",
        "operational_excellence",
        RecommendationSeverity.MEDIUM,
        "Logs scattered across per-service sinks slow incident response and obscure system-wide trends.",
        "Aggregate logs and metrics into a single destination (CloudWatch/Log Analytics/Cloud Logging or third-party) with consistent retention.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        37,
        "Manage all production infrastructure as code",
        "operational_excellence",
        RecommendationSeverity.HIGH,
        "Resources created through the console ('click-ops') are undocumented, unreviewed, and drift over time, undermining repeatability and DR.",
        "Detect console-created resources via drift detection and migrate them to Terraform / CloudFormation / Bicep / Pulumi.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        38,
        "Enable configuration-change tracking and compliance monitoring",
        "operational_excellence",
        RecommendationSeverity.MEDIUM,
        "Without a change history (AWS Config, Azure Policy/Defender for Cloud, GCP Asset Inventory), root-cause analysis for outages is slow and error-prone.",
        "Enable the native config/compliance service and wire high-severity findings into the on-call channel.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        39,
        "Document runbooks for the top incident scenarios",
        "operational_excellence",
        RecommendationSeverity.MEDIUM,
        "Teams without maintained runbooks for their top 5 incidents resolve them 2-3x slower, especially during on-call hand-offs.",
        "Author and version runbooks for the top 5 user-impacting incidents per service; review quarterly.",
        data_source=DATA_SOURCE_CONFIG,
    ),
    _rule(
        40,
        "Enable cost anomaly detection and budget alerts",
        "operational_excellence",
        RecommendationSeverity.HIGH,
        "Runaway spend (orphaned clusters, forgotten test loads, compromised credentials) can consume a month of budget in a day if undetected.",
        "Configure cost anomaly detection and per-account / per-project budget alerts at 50/80/100% thresholds.",
        data_source=DATA_SOURCE_BILLING,
    ),
]


_ALL_BUILTIN_RULE_DICTS: list[dict] = (
    _COST_RULES + _SECURITY_RULES + _RELIABILITY_RULES + _PERFORMANCE_RULES + _OPS_RULES
)


def _materialize(rule: dict) -> RecRuleResponse:
    """Return a response copy with `active` forced off when the rule's
    data source isn't ingested yet. The user can never re-enable a built-in
    via the API (the switch is read-only), so this is a one-way override."""
    if rule["data_source"] not in AVAILABLE_DATA_SOURCES:
        rule = {**rule, "active": False}
    return RecRuleResponse.model_validate(rule)


def get_builtin_rule_responses() -> list[RecRuleResponse]:
    """Return the 40 Well-Architected built-in rules as response objects."""
    return [_materialize(r) for r in _ALL_BUILTIN_RULE_DICTS]


def get_builtin_rule_by_id(rule_id: str) -> RecRuleResponse | None:
    for r in _ALL_BUILTIN_RULE_DICTS:
        if r["id"] == rule_id:
            return _materialize(r)
    return None


def is_builtin_rule_id(rule_id: str) -> bool:
    return rule_id.startswith(BUILTIN_RULE_ID_PREFIX)
