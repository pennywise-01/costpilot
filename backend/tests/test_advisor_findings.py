"""Tests for the advisor_findings module.

Covers:
    - Step 1: rename of metrics -> advisor in built-in rules.
    - Step 4: AWS Compute Optimizer finding_type -> builtin_rule_id mapping.
    - Step 3: AWS Compute Optimizer ingestor parsing of paginator output.
    - Step 5: AVAILABLE_DATA_SOURCES now activates advisor-tagged rules.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.advisor_findings.ingestors.aws_compute_optimizer import (
    AwsComputeOptimizerIngestor,
)
from app.advisor_findings.mapping import (
    ADVISOR_FINDING_TO_BUILTIN_RULE,
    AWS_COMPUTE_OPTIMIZER_MAP,
    builtin_id,
    resolve_builtin_rule_id,
)
from app.recommendation_rules.builtin_rules import (
    AVAILABLE_DATA_SOURCES,
    DATA_SOURCE_ADVISOR,
    DATA_SOURCE_BILLING,
    DATA_SOURCE_CONFIG,
    get_builtin_rule_by_id,
    get_builtin_rule_responses,
)


# ---------------------------------------------------------------------------
# Step 1 — rename
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_data_source_advisor_constant_replaces_metrics() -> None:
    """The legacy `DATA_SOURCE_METRICS` symbol must be gone, replaced by
    `DATA_SOURCE_ADVISOR` so the codebase has one canonical name."""
    import app.recommendation_rules.builtin_rules as br

    assert not hasattr(br, "DATA_SOURCE_METRICS")
    assert br.DATA_SOURCE_ADVISOR == "advisor"


@pytest.mark.unit
def test_no_builtin_rule_uses_legacy_metrics_label() -> None:
    """No built-in rule should still carry the old 'metrics' string."""
    rules = get_builtin_rule_responses()
    assert rules, "expected built-in rules to be defined"
    for rule in rules:
        assert rule.data_source != "metrics", (
            f"rule {rule.id} ({rule.name}) still uses the legacy "
            f"'metrics' data_source label"
        )


@pytest.mark.unit
def test_some_builtin_rules_now_use_advisor() -> None:
    """The renamed rules (idle compute, right-size, etc.) must be tagged
    `advisor`, not `metrics` and not `billing`."""
    advisor_rules = [
        r for r in get_builtin_rule_responses()
        if r.data_source == DATA_SOURCE_ADVISOR
    ]
    assert len(advisor_rules) >= 5, (
        "at least the previously-metrics-tagged rules should now be advisor"
    )


# ---------------------------------------------------------------------------
# Step 4 — finding-type -> rule-id mapping
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resolve_builtin_rule_id_returns_known_mapping() -> None:
    rule_id = resolve_builtin_rule_id("compute_optimizer.ec2.Idle")
    assert rule_id == builtin_id(1)  # "Terminate idle compute instances"


@pytest.mark.unit
def test_resolve_builtin_rule_id_returns_none_for_unknown() -> None:
    assert resolve_builtin_rule_id("not.a.real.finding.type") is None


@pytest.mark.unit
def test_compute_optimizer_map_targets_only_existing_builtin_rules() -> None:
    """Every mapped builtin_rule_id must resolve to a real built-in rule.
    Catches typos (wrong sequence number, missing zero-pad)."""
    for finding_type, rule_id in AWS_COMPUTE_OPTIMIZER_MAP.items():
        assert get_builtin_rule_by_id(rule_id) is not None, (
            f"finding_type {finding_type!r} maps to non-existent rule {rule_id!r}"
        )


@pytest.mark.unit
def test_compute_optimizer_map_skips_optimized_finding() -> None:
    """The 'Optimized' Compute Optimizer enum is intentionally not mapped —
    it represents an OK state with no action needed."""
    assert "compute_optimizer.ec2.Optimized" not in AWS_COMPUTE_OPTIMIZER_MAP
    assert "compute_optimizer.ebs.Optimized" not in AWS_COMPUTE_OPTIMIZER_MAP
    assert "compute_optimizer.lambda.Optimized" not in AWS_COMPUTE_OPTIMIZER_MAP


@pytest.mark.unit
def test_aggregate_mapping_includes_all_provider_maps() -> None:
    """ADVISOR_FINDING_TO_BUILTIN_RULE is the union of provider maps."""
    for k in AWS_COMPUTE_OPTIMIZER_MAP:
        assert k in ADVISOR_FINDING_TO_BUILTIN_RULE


# ---------------------------------------------------------------------------
# Step 3 — ingestor parsing
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_extract_saving_picks_largest_option() -> None:
    """`_extract_saving` should pick the largest estimatedMonthlySavings."""
    options = [
        {"savingsOpportunity": {"estimatedMonthlySavings": {"value": "12.50"}}},
        {"savingsOpportunity": {"estimatedMonthlySavings": {"value": "47.30"}}},
        {"savingsOpportunity": {"estimatedMonthlySavings": {"value": "0"}}},
    ]
    assert AwsComputeOptimizerIngestor._extract_saving(options) == 47.30


@pytest.mark.unit
def test_extract_saving_handles_missing_fields() -> None:
    assert AwsComputeOptimizerIngestor._extract_saving([]) == 0.0
    assert AwsComputeOptimizerIngestor._extract_saving([{}]) == 0.0
    assert AwsComputeOptimizerIngestor._extract_saving(
        [{"savingsOpportunity": None}]
    ) == 0.0


@pytest.mark.unit
def test_region_from_arn() -> None:
    arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-0abcd"
    assert AwsComputeOptimizerIngestor._region_from_arn(arn) == "us-east-1"
    assert AwsComputeOptimizerIngestor._region_from_arn("") == ""
    assert AwsComputeOptimizerIngestor._region_from_arn("not-an-arn") == ""


@pytest.mark.unit
def test_fetch_ec2_emits_findings_skipping_optimized() -> None:
    """Verify the ingestor parses Compute Optimizer paginator output
    correctly and skips `finding=Optimized` items."""
    ingestor = AwsComputeOptimizerIngestor()

    page = {
        "instanceRecommendations": [
            {
                "instanceArn": "arn:aws:ec2:us-east-1:1:instance/i-1",
                "instanceName": "web-1",
                "currentInstanceType": "m5.4xlarge",
                "finding": "Overprovisioned",
                "lookBackPeriodInDays": 14,
                "findingReasonCodes": ["CPUOverprovisioned"],
                "recommendationOptions": [
                    {"savingsOpportunity": {
                        "estimatedMonthlySavings": {"value": "85.00"}
                    }},
                ],
            },
            {
                "instanceArn": "arn:aws:ec2:us-east-1:1:instance/i-2",
                "finding": "Optimized",
                "recommendationOptions": [],
            },
        ]
    }
    paginator = MagicMock()
    paginator.paginate.return_value = [page]
    client = MagicMock()
    client.get_paginator.return_value = paginator

    findings = ingestor._fetch_ec2(client, account_id="111111111111")

    assert len(findings) == 1
    only = findings[0]
    assert only.finding_type == "compute_optimizer.ec2.Overprovisioned"
    assert only.resource_id == "arn:aws:ec2:us-east-1:1:instance/i-1"
    assert only.region == "us-east-1"
    assert only.estimated_saving == 85.00
    assert only.cloud == "aws_cnr"
    assert only.account_id == "111111111111"
    assert only.severity == "medium"
    assert only.raw_payload["current_type"] == "m5.4xlarge"


@pytest.mark.unit
def test_fetch_ec2_swallows_paginator_errors() -> None:
    """A failing API should not propagate; ingestor logs and returns []."""
    ingestor = AwsComputeOptimizerIngestor()
    client = MagicMock()
    client.get_paginator.side_effect = RuntimeError("AccessDenied")

    findings = ingestor._fetch_ec2(client, account_id="1")

    assert findings == []


# ---------------------------------------------------------------------------
# Step 5 — advisor-tagged rules now activate
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_available_data_sources_includes_all() -> None:
    assert DATA_SOURCE_BILLING in AVAILABLE_DATA_SOURCES
    assert DATA_SOURCE_ADVISOR in AVAILABLE_DATA_SOURCES
    assert DATA_SOURCE_CONFIG in AVAILABLE_DATA_SOURCES


@pytest.mark.unit
def test_advisor_tagged_builtin_rules_are_active() -> None:
    """With advisor in AVAILABLE_DATA_SOURCES, the previously-disabled
    advisor-tagged built-ins should report active=True."""
    advisor_rules = [
        r for r in get_builtin_rule_responses()
        if r.data_source == DATA_SOURCE_ADVISOR
    ]
    assert advisor_rules, "expected at least one advisor rule"
    assert all(r.active for r in advisor_rules), (
        "advisor-tagged built-ins should be active once their data source "
        "is in AVAILABLE_DATA_SOURCES"
    )


@pytest.mark.unit
def test_config_tagged_builtin_rules_are_active() -> None:
    """With config in AVAILABLE_DATA_SOURCES, config-tagged rules are now active."""
    config_rules = [
        r for r in get_builtin_rule_responses()
        if r.data_source == DATA_SOURCE_CONFIG
    ]
    assert config_rules, "expected config-tagged rules to exist"
    assert all(r.active for r in config_rules), (
        "config-tagged built-ins should be active once their data source "
        "is in AVAILABLE_DATA_SOURCES"
    )


# ---------------------------------------------------------------------------
# Multi-region scanning
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resolve_regions_explicit_list_takes_precedence() -> None:
    ingestor = AwsComputeOptimizerIngestor()
    session = MagicMock()
    regions = ingestor._resolve_regions(
        session,
        {"advisor_regions": ["us-west-2", "eu-central-1"]},
        primary_region="us-east-1",
    )
    assert regions == ["us-west-2", "eu-central-1"]
    # Must NOT call DescribeRegions when the user has been explicit.
    session.client.assert_not_called()


@pytest.mark.unit
def test_resolve_regions_primary_strategy_skips_discovery() -> None:
    ingestor = AwsComputeOptimizerIngestor()
    session = MagicMock()
    regions = ingestor._resolve_regions(
        session,
        {"advisor_region_strategy": "primary"},
        primary_region="ap-southeast-1",
    )
    assert regions == ["ap-southeast-1"]
    session.client.assert_not_called()


@pytest.mark.unit
def test_resolve_regions_default_discovers_via_describe_regions() -> None:
    """Default strategy is "all" — call ec2:DescribeRegions and order
    primary first, alphabetically thereafter."""
    ingestor = AwsComputeOptimizerIngestor()
    ec2 = MagicMock()
    ec2.describe_regions.return_value = {
        "Regions": [
            {"RegionName": "us-east-1", "OptInStatus": "opt-in-not-required"},
            {"RegionName": "eu-west-1", "OptInStatus": "opt-in-not-required"},
            {"RegionName": "ap-south-1", "OptInStatus": "opted-in"},
            {"RegionName": "me-south-1", "OptInStatus": "not-opted-in"},  # excluded
        ]
    }
    session = MagicMock()
    session.client.return_value = ec2

    regions = ingestor._resolve_regions(session, {}, primary_region="eu-west-1")

    # eu-west-1 is primary -> first; rest alphabetical; me-south-1 dropped.
    assert regions == ["eu-west-1", "ap-south-1", "us-east-1"]


@pytest.mark.unit
def test_resolve_regions_caps_at_max_regions() -> None:
    """A misconfigured account with 30 enabled regions must not spawn 30
    parallel scans."""
    from app.advisor_findings.ingestors.aws_compute_optimizer import _MAX_REGIONS

    ingestor = AwsComputeOptimizerIngestor()
    explicit = [f"region-{i:02d}" for i in range(30)]
    regions = ingestor._resolve_regions(
        MagicMock(),
        {"advisor_regions": explicit},
        primary_region="region-00",
    )
    assert len(regions) == _MAX_REGIONS


@pytest.mark.unit
def test_resolve_regions_falls_back_to_primary_on_describe_failure() -> None:
    """If DescribeRegions errors (e.g. AccessDenied), we still produce a
    useful scan instead of an empty one."""
    ingestor = AwsComputeOptimizerIngestor()
    ec2 = MagicMock()
    ec2.describe_regions.side_effect = RuntimeError("AccessDenied")
    session = MagicMock()
    session.client.return_value = ec2

    regions = ingestor._resolve_regions(session, {}, primary_region="us-east-2")

    assert regions == ["us-east-2"]


@pytest.mark.unit
def test_fetch_for_region_aggregates_all_three_resource_families() -> None:
    """`_fetch_for_region` should call EC2, EBS, and Lambda fetchers and
    stamp every emitted finding with the call-site region."""
    ingestor = AwsComputeOptimizerIngestor()

    ec2_paginator = MagicMock()
    ec2_paginator.paginate.return_value = [{
        "instanceRecommendations": [{
            "instanceArn": "arn:aws:ec2:eu-west-2:1:instance/i-1",
            "finding": "Overprovisioned",
            "recommendationOptions": [{
                "savingsOpportunity": {"estimatedMonthlySavings": {"value": "10"}}
            }],
        }]
    }]
    ebs_paginator = MagicMock()
    ebs_paginator.paginate.return_value = [{"volumeRecommendations": []}]
    lambda_paginator = MagicMock()
    lambda_paginator.paginate.return_value = [{"lambdaFunctionRecommendations": []}]

    co_client = MagicMock()
    co_client.get_paginator.side_effect = lambda name: {
        "get_ec2_instance_recommendations": ec2_paginator,
        "get_ebs_volume_recommendations": ebs_paginator,
        "get_lambda_function_recommendations": lambda_paginator,
    }[name]

    session = MagicMock()
    session.client.return_value = co_client

    findings = ingestor._fetch_for_region(session, "eu-west-2", "111111111111")

    assert len(findings) == 1
    # Region must come from the call-site, NOT the ARN, so a multi-region
    # estate stamps findings with the API endpoint that produced them.
    assert findings[0].region == "eu-west-2"
    session.client.assert_called_once_with(
        "compute-optimizer", region_name="eu-west-2"
    )


@pytest.mark.unit
def test_fetch_sync_fans_out_across_resolved_regions() -> None:
    """End-to-end check: _fetch_sync resolves regions then merges
    findings from each region's parallel scan."""
    ingestor = AwsComputeOptimizerIngestor()

    captured_regions: list[str] = []

    def fake_for_region(_session, region, _account_id):
        captured_regions.append(region)
        from app.advisor_findings.schemas import NormalizedAdvisorFinding
        return [NormalizedAdvisorFinding(
            cloud="aws_cnr",
            account_id="111111111111",
            source_service="AWS Compute Optimizer",
            finding_type="compute_optimizer.ec2.Overprovisioned",
            resource_id=f"arn:aws:ec2:{region}:1:instance/i-1",
            region=region,
            severity="medium",
            estimated_saving=1.0,
        )]

    sts = MagicMock()
    sts.get_caller_identity.return_value = {"Account": "111111111111"}
    fake_session = MagicMock()
    fake_session.client.return_value = sts

    class FakeAdapter:
        def __init__(self, _cfg): pass
        def _get_session(self): return fake_session

    with patch("app.cloud_accounts.adapters.aws.AWSAdapter", FakeAdapter), \
         patch.object(ingestor, "_fetch_for_region", side_effect=fake_for_region), \
         patch.object(
             ingestor, "_resolve_regions",
             return_value=["us-east-1", "eu-west-1", "ap-south-1"],
         ):
        findings = ingestor._fetch_sync({
            "access_key_id": "AKIA",
            "secret_access_key": "s",
            "region": "us-east-1",
        })

    assert len(findings) == 3
    assert sorted(captured_regions) == ["ap-south-1", "eu-west-1", "us-east-1"]
    assert {f.region for f in findings} == {"us-east-1", "eu-west-1", "ap-south-1"}
