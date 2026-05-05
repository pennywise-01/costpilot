# Rule Data-Source Strategy

How CostPilot will eventually power the 33 built-in rules that can't run on billing data alone — without crawling raw CloudWatch / Azure Monitor / Cloud Monitoring (rate-limit hell) and without giving CostPilot admin credentials.

## Problem

Today only 7 of the 40 built-in rules can be evaluated from BigQuery billing exports. The other 33 (most security, reliability, performance, ops-excellence rules) need utilization or resource-state data. Naive approach = polling CloudWatch / Azure Monitor / Cloud Monitoring at scale = expensive + throttled + lots of code per rule.

## Three data layers per provider

| Layer | AWS | Azure | GCP |
|---|---|---|---|
| **Pre-computed advisors** *(best ROI)* | Compute Optimizer, Trusted Advisor, Cost Optimization Hub, IAM Access Analyzer | Azure Advisor, Defender for Cloud | Recommender API, Active Assist |
| **Asset / state inventory** | AWS Config, Resource Explorer | Resource Graph (KQL) | **Cloud Asset Inventory (native BigQuery export)** |
| **Raw metrics** *(only when above don't cover)* | CloudWatch (prefer Metric Streams) | Azure Monitor | Cloud Monitoring |

Key insight: **the cloud providers have already computed "this VM is idle / this disk is unused / this IAM role is over-privileged"** and expose it via advisor APIs. Single bulk call per account per day = no rate-limit issues, no per-rule logic.

## Tiered rollout plan

### Tier 1 — Provider Advisor APIs (~1 week per CSP)

One scheduled job per cloud account per day. Map each advisor finding type to a built-in rule ID, persist into a single normalized BigQuery table (e.g. `advisor_findings`).

- **AWS** — Compute Optimizer (`GetEC2InstanceRecommendations`, `GetEBSVolumeRecommendations`, `GetLambdaFunctionRecommendations`) + Trusted Advisor (`DescribeTrustedAdvisorChecks` + `DescribeTrustedAdvisorCheckResult`) + Cost Optimization Hub (`ListRecommendations`).
- **Azure** — Advisor REST API (`recommendationsList`).
- **GCP** — Recommender API (`google.cloud.recommender.v1.Recommender`).

**Coverage:** activates ~12 of the 33 inactive rules (idle compute, rightsizing, unattached volumes, idle LBs, RI/SP underutilization, IAM key rotation, public buckets, MFA gaps, etc.).

### Tier 2 — Asset / State Inventory (~2 weeks)

Snapshot resource configuration daily into BigQuery. Same data model as billing: append-only daily snapshots, query with SQL.

- **GCP** — `Cloud Asset Inventory → BigQuery export` is **native** (one Terraform resource). Cheapest path to GCP config rules.
- **AWS** — AWS Config aggregator → S3 → mirror to BigQuery via Storage Transfer Service, **or** Resource Explorer + scheduled Lambda.
- **Azure** — Resource Graph KQL queries on demand → small ETL job persists results to BigQuery.

**Coverage:** activates remaining security, reliability, and ops-excellence rules (multi-AZ flag, encryption at rest, SG/NSG open ports, tag presence, naming, IaC drift, etc.).

### Tier 3 — Custom raw metrics (only if needed)

For rules advisors don't cover. Use streaming where possible:

- **AWS** — CloudWatch Metric Streams → Kinesis Firehose → S3/BigQuery (push-based, no polling, no rate limit).
- **Azure** — Diagnostic settings → Event Hub.
- **GCP** — Cloud Monitoring export → Pub/Sub → BigQuery.

Most rules will never need this tier.

## Read-only IAM design (NOT admin)

Customers grant CostPilot a scoped read-only role per cloud:

- **AWS** — managed `SecurityAudit` + `ViewOnlyAccess`, plus narrow `compute-optimizer:Get*`, `trustedadvisor:Describe*`, `ce:Get*`, `cost-optimization-hub:Get*`. External-ID-protected cross-account assume role.
- **Azure** — built-in `Reader` at subscription scope + `Cost Management Reader` + `Microsoft.Advisor/*/read`.
- **GCP** — service account with `roles/viewer` + `roles/recommender.viewer` + `roles/cloudasset.viewer` + `roles/billing.viewer`. Use workload identity federation, not service-account keys.

## Rate-limit mitigations

- **Use advisors, not raw metrics.** One `GetEC2InstanceRecommendations` call returns thousands of pre-scored instances; the equivalent CloudWatch crawl = thousands of `GetMetricData` calls.
- **Stream over poll.** CloudWatch Metric Streams / Azure Diagnostic Settings / GCP Pub/Sub exports are push-based.
- **Daily snapshots.** Resource state changes slowly. A daily refresh is plenty for the rules we have.
- **Per-account exponential backoff** on every advisor/inventory call.
- **Run scans during off-hours** for the customer's primary region.

## Reframing the internal labels

Today the codebase has three labels: `billing`, `metrics`, `config`. The **`metrics` label is misleading** — most rules tagged `metrics` are actually satisfied by **advisor APIs**, not raw CloudWatch. Two future-friendly options:

- **Option A (minimal):** keep the three labels, but document that `metrics` = "satisfied by provider advisor APIs (Compute Optimizer / Azure Advisor / GCP Recommender)".
- **Option B (clearer):** rename `metrics` → `advisor`, keep `config` as-is. UI badge becomes `Needs: Advisor` / `Needs: Config`. One-line change in `builtin_rules.py` + matching frontend constant.

Recommend Option B before any Tier-1 ingestor lands, so the UI matches what we'll actually build.

## What this means for the 80% engineering cost reduction

The naive plan (build per-rule CloudWatch / Azure Monitor / Cloud Monitoring evaluators) is roughly:

- 1 evaluator × 33 rules × 3 clouds × test/maintenance burden = many person-months.

The advisor-first plan is roughly:

- 3 advisor ingestors (one per CSP) + 1 mapping table from advisor finding type → built-in rule ID.
- 3 inventory ingestors (Tier 2) + a handful of SQL views over the inventory snapshots.

Same coverage, ~5-10× less code, far better resilience to provider rate limits and SDK churn.

## Next concrete steps (when ready to start)

1. Rename `metrics` label to `advisor` in `builtin_rules.py` + `RecommendationRules.tsx` (cosmetic, ~5 lines).
2. Define the `advisor_findings` BigQuery table schema (one row per finding, columns: `cloud`, `account_id`, `finding_type`, `resource_id`, `region`, `severity`, `estimated_saving`, `raw_payload`, `observed_at`).
3. Build the AWS Compute Optimizer ingestor first — highest signal density per API call, easiest to test against a real account.
4. Add a mapping table `advisor_finding_type → builtin_rule_id` to translate raw provider findings into our internal rule keys.
5. Flip `AVAILABLE_DATA_SOURCES` to include `advisor` once Step 3 is producing data.
