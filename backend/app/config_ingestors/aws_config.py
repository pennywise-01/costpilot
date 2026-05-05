"""AWS Config ingestor (Tier-2 asset/state inventory).

Pulls a resource-configuration snapshot from AWS Config aggregator
(`config:SelectAggregateResourceConfig` or `config:SelectResourceConfig`)
and normalizes each resource into `NormalizedResourceConfig`.

Uses the same boto3 session pattern as the AWS Compute Optimizer
ingestor so assume-role accounts work transparently.

Required IAM: the actions in `AWS_CONFIG_ACTIONS` (config:Describe*,
config:Select*, iam:List*, ec2:DescribeSecurityGroups, etc.).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.config_ingestors.base import ConfigIngestor
from app.config_ingestors.schemas import NormalizedResourceConfig

logger = logging.getLogger(__name__)

_DEFAULT_REGION = "us-east-1"

_RESOURCE_TYPES: list[str] = [
    "AWS::EC2::Instance",
    "AWS::EC2::Volume",
    "AWS::EC2::SecurityGroup",
    "AWS::EC2::NetworkInterface",
    "AWS::RDS::DBInstance",
    "AWS::RDS::DBSnapshot",
    "AWS::Lambda::Function",
    "AWS::S3::Bucket",
    "AWS::IAM::User",
    "AWS::IAM::Role",
    "AWS::EBS::Snapshot",
]


class AwsConfigIngestor(ConfigIngestor):
    """Pulls resource config from AWS Config."""

    source_service = "AWS Config"

    async def fetch(self, config: dict) -> list[NormalizedResourceConfig]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("AWS Config ingestion failed")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedResourceConfig]:
        from app.cloud_accounts.adapters.aws import AWSAdapter

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
                "role_session_name", "CostPilotConfig",
            ),
            "region": primary_region,
        }
        adapter = AWSAdapter(adapter_config)
        session = adapter._get_session()

        sts_client = session.client("sts", region_name=primary_region)
        try:
            account_id = sts_client.get_caller_identity().get("Account", "")
        except Exception as e:
            logger.warning("AWS Config: STS get_caller_identity failed: %s", e)
            account_id = ""

        observed_at = datetime.now(timezone.utc)
        config_client = session.client("config", region_name=primary_region)
        results: list[NormalizedResourceConfig] = []

        for resource_type in _RESOURCE_TYPES:
            try:
                paginator = config_client.get_paginator("list_discovered_resources")
                for page in paginator.paginate(resourceType=resource_type):
                    for res in page.get("resourceIdentifiers", []):
                        resource_id = res.get("resourceId", "")
                        region = res.get("resourceName", "")  # Config uses resourceName for region-like info
                        
                        try:
                            detail_resp = config_client.get_resource_config_history(
                                resourceType=resource_type,
                                resourceId=resource_id,
                                limit=1,
                            )
                            items = detail_resp.get("configurationItems", [])
                            props: dict[str, Any] = {}
                            tags: dict[str, str] = {}
                            if items:
                                item = items[0]
                                props = _parse_configuration(item.get("configuration", "{}"))
                                tags = _parse_tags(item.get("tags", {}))
                        except Exception:
                            props = {}
                            tags = {}

                        results.append(NormalizedResourceConfig(
                            cloud="aws_cnr",
                            account_id=account_id,
                            source_service=self.source_service,
                            resource_id=resource_id,
                            resource_type=resource_type,
                            region=region,
                            properties=props,
                            tags=tags,
                            observed_at=observed_at,
                        ))
            except Exception as e:
                logger.debug(
                    "AWS Config: list_discovered_resources failed for %s: %s",
                    resource_type, e,
                )

        logger.info(
            "AWS Config ingest: %d resources for account %s",
            len(results), account_id or "<unknown>",
        )
        return results


def _parse_configuration(config_str: str) -> dict[str, Any]:
    import json
    try:
        return json.loads(config_str) if isinstance(config_str, str) else config_str
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_tags(tags: list[dict] | dict) -> dict[str, str]:
    if isinstance(tags, dict):
        return {str(k): str(v) for k, v in tags.items()}
    if isinstance(tags, list):
        return {
            t.get("key", ""): t.get("value", "")
            for t in tags
            if isinstance(t, dict)
        }
    return {}
