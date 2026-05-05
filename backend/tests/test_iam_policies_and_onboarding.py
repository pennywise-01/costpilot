"""Tests for the IAM policy registry, AWS adapter assume-role support,
Compute Optimizer enrollment preflight, and the ingestor's credential
propagation.

These tests cover the "how will users configure it?" follow-up to the
advisor-findings work — specifically:

    - iam_policies.build_policy() returns well-formed docs per cloud/tier
    - AWSAdapter accepts role_arn + external_id and calls sts:AssumeRole
    - AWSAdapter raises BadRequestError when NO credentials are supplied
    - Compute Optimizer enrollment preflight emits a warning (not a hard
      failure) when the account is not enrolled
    - AwsComputeOptimizerIngestor reuses the adapter's session, so
      assume-role accounts get temp credentials end-to-end
"""

from unittest.mock import MagicMock, patch

import pytest

from app.cloud_accounts.iam_policies import (
    AWS_ADVISOR_ACTIONS,
    AWS_BILLING_ACTIONS,
    VALID_TIERS,
    build_aws_policy_document,
    build_policy,
)


# ---------------------------------------------------------------------------
# IAM policy registry
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_aws_advisor_actions_include_compute_optimizer_enrollment() -> None:
    """Must include enrollment action or the preflight check reports a
    spurious missing-permission warning."""
    assert "compute-optimizer:GetEnrollmentStatus" in AWS_ADVISOR_ACTIONS


@pytest.mark.unit
def test_aws_advisor_actions_include_trusted_advisor_and_coh() -> None:
    """All Tier-1 providers we've mapped in mapping.py need coverage in
    the published policy."""
    assert any(a.startswith("support:") for a in AWS_ADVISOR_ACTIONS)
    assert any(
        a.startswith("cost-optimization-hub:") for a in AWS_ADVISOR_ACTIONS
    )


@pytest.mark.unit
def test_build_aws_policy_deduplicates_and_sorts() -> None:
    doc = build_aws_policy_document(["billing", "advisor", "billing"])
    assert doc["Version"] == "2012-10-17"
    actions = doc["Statement"][0]["Action"]
    assert actions == sorted(actions), "actions must be sorted for stable diffs"
    assert len(actions) == len(set(actions)), "no duplicates"


@pytest.mark.unit
def test_build_aws_policy_respects_tier_selection() -> None:
    billing_only = build_aws_policy_document(["billing"])
    billing_actions = set(billing_only["Statement"][0]["Action"])
    assert "ce:GetCostAndUsage" in billing_actions
    assert "compute-optimizer:GetEC2InstanceRecommendations" not in billing_actions

    advisor = build_aws_policy_document(["advisor"])
    advisor_actions = set(advisor["Statement"][0]["Action"])
    assert "compute-optimizer:GetEC2InstanceRecommendations" in advisor_actions
    assert "ce:GetCostAndUsage" not in advisor_actions


@pytest.mark.unit
def test_build_aws_policy_with_trust_principal_emits_trust_policy() -> None:
    doc = build_aws_policy_document(
        ["billing"],
        trust_principal="arn:aws:iam::111111111111:root",
        external_id="org-abc",
    )
    assert "Policy" in doc and "TrustPolicy" in doc
    stmt = doc["TrustPolicy"]["Statement"][0]
    assert stmt["Action"] == "sts:AssumeRole"
    assert stmt["Principal"] == {"AWS": "arn:aws:iam::111111111111:root"}
    assert stmt["Condition"]["StringEquals"]["sts:ExternalId"] == "org-abc"


@pytest.mark.unit
def test_build_policy_dispatches_by_cloud_alias() -> None:
    aws = build_policy("aws", ["billing"])
    assert aws["Version"] == "2012-10-17"

    azure = build_policy("azure", ["billing", "advisor"])
    assert azure["cloud"] == "azure"
    assert "Cost Management Reader" in azure["roles"]
    assert "Reader" in azure["roles"]

    gcp = build_policy("gcp", ["advisor"])
    assert gcp["cloud"] == "gcp"
    assert "roles/recommender.viewer" in gcp["roles"]


@pytest.mark.unit
def test_build_policy_rejects_empty_tier_set() -> None:
    with pytest.raises(ValueError):
        build_policy("aws", [])
    with pytest.raises(ValueError):
        build_policy("aws", ["bogus"])


@pytest.mark.unit
def test_valid_tiers_match_data_source_constants() -> None:
    """The tier names advertised to users must match the backend
    data_source strings used by built-in rules, so a user who grants the
    'advisor' tier actually activates advisor-tagged rules."""
    from app.recommendation_rules.builtin_rules import (
        DATA_SOURCE_ADVISOR,
        DATA_SOURCE_BILLING,
        DATA_SOURCE_CONFIG,
    )
    assert VALID_TIERS == {
        DATA_SOURCE_BILLING, DATA_SOURCE_ADVISOR, DATA_SOURCE_CONFIG,
    }


# ---------------------------------------------------------------------------
# AWSAdapter auth modes
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_aws_adapter_requires_some_credentials() -> None:
    from app.cloud_accounts.adapters.aws import AWSAdapter
    from app.shared.exceptions import BadRequestError

    with pytest.raises(BadRequestError):
        AWSAdapter({})


@pytest.mark.unit
def test_aws_adapter_accepts_static_keys() -> None:
    from app.cloud_accounts.adapters.aws import AWSAdapter

    adapter = AWSAdapter({
        "access_key_id": "AKIA...",
        "secret_access_key": "secret",
        "region": "eu-west-1",
    })
    assert adapter.access_key_id == "AKIA..."
    assert adapter.role_arn == ""


@pytest.mark.unit
def test_aws_adapter_accepts_role_arn_without_static_keys() -> None:
    from app.cloud_accounts.adapters.aws import AWSAdapter

    adapter = AWSAdapter({
        "role_arn": "arn:aws:iam::123456789012:role/CostPilotReadOnly",
        "external_id": "org-abc",
    })
    assert adapter.role_arn.endswith(":role/CostPilotReadOnly")
    assert adapter.external_id == "org-abc"
    assert adapter.access_key_id == ""


@pytest.mark.unit
def test_aws_adapter_assume_role_uses_external_id_and_session_name() -> None:
    """When role_arn is set, _get_session must call sts.assume_role with
    the configured ExternalId and return a session built from temp creds."""
    from app.cloud_accounts.adapters.aws import AWSAdapter

    adapter = AWSAdapter({
        "access_key_id": "AKIA",
        "secret_access_key": "sec",
        "role_arn": "arn:aws:iam::111111111111:role/CostPilotReadOnly",
        "external_id": "ext-xyz",
        "role_session_name": "TestSession",
    })

    fake_sts = MagicMock()
    fake_sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIA_TEMP",
            "SecretAccessKey": "temp_secret",
            "SessionToken": "tok",
        }
    }

    # Two boto3.Session instances are created by _assume_role_session:
    # (1) bootstrap session (static keys) whose .client("sts") we intercept
    # (2) final session wrapping the temp creds -- we just assert on args.
    bootstrap = MagicMock()
    bootstrap.client.return_value = fake_sts
    final = MagicMock()

    with patch(
        "app.cloud_accounts.adapters.aws.boto3.Session",
        side_effect=[bootstrap, final],
    ) as session_ctor:
        session = adapter._get_session()

    assert session is final
    fake_sts.assume_role.assert_called_once()
    kwargs = fake_sts.assume_role.call_args.kwargs
    assert kwargs["RoleArn"].endswith(":role/CostPilotReadOnly")
    assert kwargs["ExternalId"] == "ext-xyz"
    assert kwargs["RoleSessionName"] == "TestSession"

    # Final session must be built from the temporary credentials.
    final_call_kwargs = session_ctor.call_args_list[1].kwargs
    assert final_call_kwargs["aws_access_key_id"] == "ASIA_TEMP"
    assert final_call_kwargs["aws_session_token"] == "tok"


@pytest.mark.unit
def test_aws_adapter_assume_role_without_external_id() -> None:
    """ExternalId is optional on sts:AssumeRole (e.g. self-hosted
    deployments trusting their own account)."""
    from app.cloud_accounts.adapters.aws import AWSAdapter

    adapter = AWSAdapter({
        "role_arn": "arn:aws:iam::1:role/R",
        "access_key_id": "AKIA",
        "secret_access_key": "s",
    })

    fake_sts = MagicMock()
    fake_sts.assume_role.return_value = {
        "Credentials": {"AccessKeyId": "a", "SecretAccessKey": "b", "SessionToken": "c"}
    }
    bootstrap = MagicMock()
    bootstrap.client.return_value = fake_sts
    final = MagicMock()

    with patch(
        "app.cloud_accounts.adapters.aws.boto3.Session",
        side_effect=[bootstrap, final],
    ):
        adapter._get_session()

    assert "ExternalId" not in fake_sts.assume_role.call_args.kwargs


# ---------------------------------------------------------------------------
# Compute Optimizer enrollment preflight
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrollment_preflight_warns_when_inactive() -> None:
    """When Compute Optimizer is reachable but not enrolled, the adapter
    must emit a human-readable warning, not a hard AccessDenied. This
    lets onboarding succeed while prompting the user to opt in."""
    from app.cloud_accounts.adapters.aws import AWSAdapter

    adapter = AWSAdapter({
        "access_key_id": "AKIA",
        "secret_access_key": "s",
    })

    # Stub the permission exercises so only the enrollment branch runs.
    # We short-circuit MINIMUM_PERMISSIONS to just the CO check.
    with patch.object(
        AWSAdapter, "MINIMUM_PERMISSIONS", ["compute-optimizer:GetEnrollmentStatus"]
    ):
        co_client = MagicMock()
        co_client.get_enrollment_status.return_value = {"status": "Inactive"}
        with patch.object(adapter, "_get_client", return_value=co_client):
            missing = await adapter._validate_permissions()

    assert len(missing) == 1
    assert "NotEnrolled" in missing[0]
    assert "Inactive" in missing[0]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrollment_preflight_silent_when_active() -> None:
    from app.cloud_accounts.adapters.aws import AWSAdapter

    adapter = AWSAdapter({
        "access_key_id": "AKIA",
        "secret_access_key": "s",
    })

    with patch.object(
        AWSAdapter, "MINIMUM_PERMISSIONS", ["compute-optimizer:GetEnrollmentStatus"]
    ):
        co_client = MagicMock()
        co_client.get_enrollment_status.return_value = {"status": "Active"}
        with patch.object(adapter, "_get_client", return_value=co_client):
            missing = await adapter._validate_permissions()

    assert missing == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrollment_preflight_records_access_denied_as_missing_permission() -> None:
    """If the IAM role lacks compute-optimizer:GetEnrollmentStatus, we
    want the raw permission name reported so the policy-JSON endpoint's
    output maps 1:1 to the warning."""
    from botocore.exceptions import ClientError

    from app.cloud_accounts.adapters.aws import AWSAdapter

    adapter = AWSAdapter({
        "access_key_id": "AKIA",
        "secret_access_key": "s",
    })

    err = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "GetEnrollmentStatus",
    )

    with patch.object(
        AWSAdapter, "MINIMUM_PERMISSIONS", ["compute-optimizer:GetEnrollmentStatus"]
    ):
        co_client = MagicMock()
        co_client.get_enrollment_status.side_effect = err
        with patch.object(adapter, "_get_client", return_value=co_client):
            missing = await adapter._validate_permissions()

    assert missing == ["compute-optimizer:GetEnrollmentStatus"]


# ---------------------------------------------------------------------------
# Ingestor <-> adapter credential propagation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ingestor_passes_role_arn_through_to_adapter() -> None:
    """The ingestor must reuse AWSAdapter so assume-role accounts get
    temp credentials end-to-end instead of silently falling back to
    empty static keys."""
    from app.advisor_findings.ingestors.aws_compute_optimizer import (
        AwsComputeOptimizerIngestor,
    )

    ingestor = AwsComputeOptimizerIngestor()

    captured_config: dict = {}

    class FakeAdapter:
        def __init__(self, cfg):
            captured_config.update(cfg)

        def _get_session(self):
            sess = MagicMock()
            co = MagicMock()
            # Empty paginator -> ingestor exits cleanly after STS call.
            paginator = MagicMock()
            paginator.paginate.return_value = []
            co.get_paginator.return_value = paginator
            sts = MagicMock()
            sts.get_caller_identity.return_value = {"Account": "111111111111"}
            sess.client.side_effect = lambda svc, **_: {
                "compute-optimizer": co,
                "sts": sts,
            }[svc]
            return sess

    with patch(
        "app.cloud_accounts.adapters.aws.AWSAdapter",
        FakeAdapter,
    ):
        findings = ingestor._fetch_sync({
            "role_arn": "arn:aws:iam::111:role/CP",
            "external_id": "ext",
            "region": "us-west-2",
        })

    assert findings == []
    assert captured_config["role_arn"].endswith(":role/CP")
    assert captured_config["external_id"] == "ext"
    assert captured_config["region"] == "us-west-2"
    # Must NOT leak empty static keys when role_arn is set, otherwise
    # AWSAdapter's "require credentials" guard silently accepts them.
    assert captured_config["access_key_id"] == ""
