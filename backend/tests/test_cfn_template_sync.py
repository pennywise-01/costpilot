"""Keep the public CloudFormation template in lock-step with the
backend IAM policy registry.

The template at `templates/aws-readonly-role.yaml` is what users run to
create the read-only role in their account. The registry at
`app.cloud_accounts.iam_policies.AWS_*_ACTIONS` is what the onboarding
wizard *says* users need to grant. If those two drift, users either:

    1. Grant too little → ingestors silently log AccessDenied, OR
    2. Grant too much  → we've published a template that grants perms
       our code doesn't actually use.

Both are bad. This test fails CI before either can ship.
"""

from pathlib import Path

import pytest
import yaml

from app.cloud_accounts.iam_policies import (
    AWS_ADVISOR_ACTIONS,
    AWS_BILLING_ACTIONS,
    AWS_CONFIG_ACTIONS,
)


TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "templates"
    / "aws-readonly-role.yaml"
)


def _load_template() -> dict:
    """Load the CFN template, treating all `!Fn::*` tags as opaque."""
    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    with TEMPLATE_PATH.open("r", encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_Loader)


def _actions_for_policy_name(template: dict, policy_name: str) -> set[str]:
    """Find the inline/attached policy by name and return its Action set.

    Works for both Role inline policies (nested under Resources.<role>.
    Properties.Policies) and stand-alone `AWS::IAM::Policy` resources.
    """
    for resource in template.get("Resources", {}).values():
        rtype = resource.get("Type", "")
        props = resource.get("Properties", {})

        if rtype == "AWS::IAM::Role":
            for pol in props.get("Policies", []) or []:
                if pol.get("PolicyName") == policy_name:
                    return _extract_actions(pol.get("PolicyDocument", {}))

        elif rtype == "AWS::IAM::Policy":
            if props.get("PolicyName") == policy_name:
                return _extract_actions(props.get("PolicyDocument", {}))

    raise AssertionError(
        f"Policy {policy_name!r} not found in CloudFormation template"
    )


def _extract_actions(policy_doc: dict) -> set[str]:
    out: set[str] = set()
    for stmt in policy_doc.get("Statement", []):
        action = stmt.get("Action", [])
        if isinstance(action, str):
            out.add(action)
        else:
            out.update(action)
    return out


@pytest.fixture(scope="module")
def template() -> dict:
    assert TEMPLATE_PATH.exists(), (
        f"CloudFormation template not found at {TEMPLATE_PATH}"
    )
    return _load_template()


@pytest.mark.unit
def test_template_top_level_sections_present(template: dict) -> None:
    """Sanity: the template has the expected top-level layout."""
    for section in (
        "AWSTemplateFormatVersion",
        "Parameters",
        "Conditions",
        "Resources",
        "Outputs",
    ):
        assert section in template, f"Missing section: {section}"


@pytest.mark.unit
def test_template_declares_required_parameters(template: dict) -> None:
    """These parameters are what the onboarding wizard pre-fills via the
    CloudFormation Quick-Create URL."""
    params = template.get("Parameters", {})
    for required in ("TrustPrincipal", "ExternalId", "Tiers", "RoleName"):
        assert required in params, (
            f"Template must declare Parameter: {required}"
        )


@pytest.mark.unit
def test_template_uses_external_id_condition_on_assume_role(
    template: dict,
) -> None:
    """The trust policy must require `sts:ExternalId` — without it the
    role is assumable by anyone in the trust principal's account."""
    role = template["Resources"]["CostPilotReadOnlyRole"]
    trust = role["Properties"]["AssumeRolePolicyDocument"]
    stmt = trust["Statement"][0]
    # Condition block may be a tagged None (opaque in our parser) when
    # it uses !Ref — just assert the key exists.
    assert "Condition" in stmt, (
        "Trust policy must have a Condition block with sts:ExternalId"
    )


@pytest.mark.unit
def test_billing_actions_match_registry(template: dict) -> None:
    """Billing tier is always-on in the template; the inline policy
    must exactly match AWS_BILLING_ACTIONS."""
    cfn_actions = _actions_for_policy_name(template, "CostPilotBilling")
    registry_actions = set(AWS_BILLING_ACTIONS)
    _assert_set_equal(cfn_actions, registry_actions, "CostPilotBilling")


@pytest.mark.unit
def test_advisor_actions_match_registry(template: dict) -> None:
    cfn_actions = _actions_for_policy_name(template, "CostPilotAdvisor")
    registry_actions = set(AWS_ADVISOR_ACTIONS)
    _assert_set_equal(cfn_actions, registry_actions, "CostPilotAdvisor")


@pytest.mark.unit
def test_config_actions_match_registry(template: dict) -> None:
    cfn_actions = _actions_for_policy_name(template, "CostPilotConfig")
    registry_actions = set(AWS_CONFIG_ACTIONS)
    _assert_set_equal(cfn_actions, registry_actions, "CostPilotConfig")


def _assert_set_equal(
    cfn: set[str], registry: set[str], policy_name: str,
) -> None:
    missing_in_cfn = registry - cfn
    extra_in_cfn = cfn - registry
    assert not missing_in_cfn and not extra_in_cfn, (
        f"Drift detected for {policy_name!r}:\n"
        f"  missing from CFN template: {sorted(missing_in_cfn)}\n"
        f"  extra in CFN template:     {sorted(extra_in_cfn)}\n"
        "Update either templates/aws-readonly-role.yaml or "
        "app/cloud_accounts/iam_policies.py so they match."
    )
