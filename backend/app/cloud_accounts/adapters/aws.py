"""AWS Cloud Adapter - Fetches real cost and resource data from AWS."""

import asyncio
import json
import logging
import re
from datetime import timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.cloud_accounts.adapters.base import CloudAdapter
from app.shared.circuit_breaker import aws_circuit_breaker
from app.shared.exceptions import BadRequestError
from app.shared.retry import AWS_RETRY_CONFIG, with_retry
from app.shared.utils.time import utc_now


def _sanitize_csp_error(error: Exception) -> str:
    """Sanitize cloud provider error messages to prevent information leakage."""
    error_str = str(error)
    # Remove AWS account IDs
    error_str = re.sub(r'\b\d{12}\b', '***REDACTED***', error_str)
    # Remove ARNs
    error_str = re.sub(r'arn:aws:[^:\s]+:[^:\s]+:\d{12}:[^/\s]+', '***REDACTED***', error_str)
    # Remove Azure subscription IDs (GUIDs in certain contexts)
    error_str = re.sub(r'subscription[^:]*:?[\s"]*([0-9a-fA-F-]{36})', 'subscription_id: ***REDACTED***', error_str)
    # Remove GCP project IDs/numbers
    error_str = re.sub(r'project[-_]?[nN]umbers?[/\s]+(\d{6,})', 'project_number: ***REDACTED***', error_str)
    # Remove full error details, return generic message
    return "Cloud provider API error. Check server logs for details."


class AWSAdapter(CloudAdapter):
    """Adapter for AWS cloud accounts using boto3."""

    MINIMUM_PERMISSIONS = [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast",
        "ec2:DescribeInstances",
        "ec2:DescribeRegions",
        "rds:DescribeDBInstances",
        "lambda:ListFunctions",
        "s3:ListAllMyBuckets",
    ]

    def __init__(self, config: dict):
        """Initialize with decrypted config containing AWS credentials.

        Expected config keys:
        - access_key_id: AWS access key ID
        - secret_access_key: AWS secret access key
        - region: Default AWS region (optional, defaults to us-east-1)
        """
        self.access_key_id = config.get("access_key_id", "")
        self.secret_access_key = config.get("secret_access_key", "")
        self.region = config.get("region", "us-east-1")
        self.account_id = config.get("account_id", "")
        self._permission_warnings: list[str] = []

        if not self.access_key_id or not self.secret_access_key:
            raise BadRequestError("AWS credentials (access_key_id and secret_access_key) are required")

    def _get_session(self) -> boto3.Session:
        """Create a boto3 session with the stored credentials."""
        return boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
        )

    def _get_client(self, service: str, region: str | None = None):
        """Get a boto3 client for the specified service."""
        session = self._get_session()
        return session.client(service, region_name=region or self.region)

    async def validate_credentials(self) -> dict[str, Any]:
        """Validate AWS credentials by calling STS GetCallerIdentity.

        Returns:
            dict with 'valid' (bool) and 'permission_warnings' (list[str])
        """
        try:
            async def _api_call():
                return await asyncio.to_thread(self._validate_credentials_sync)

            await with_retry(
                lambda: aws_circuit_breaker.call(_api_call),
                config=AWS_RETRY_CONFIG,
            )
            # After identity validation, check permissions
            missing = await self._validate_permissions()
            if missing:
                logger.warning(f"Credentials missing permissions: {missing}")
                self._permission_warnings = missing
            return {"valid": True, "permission_warnings": self._permission_warnings}
        except (ClientError, NoCredentialsError) as e:
            raise BadRequestError(_sanitize_csp_error(e))
        except Exception as e:
            raise BadRequestError(_sanitize_csp_error(e))

    def _validate_credentials_sync(self) -> bool:
        """Synchronous credential validation."""
        sts = self._get_client("sts")
        identity = sts.get_caller_identity()
        self.account_id = identity.get("Account", "")
        return True

    async def _validate_permissions(self) -> list[str]:
        """Check minimum required permissions."""
        missing = []
        for perm in self.MINIMUM_PERMISSIONS:
            try:
                if perm == "ce:GetCostAndUsage" or perm == "ce:GetCostForecast":
                    # Cost Explorer - try a minimal query
                    ce = self._get_client("ce", region="us-east-1")
                    ce.get_cost_and_usage(
                        TimePeriod={"Start": "2025-01-01", "End": "2025-01-02"},
                        Granularity="DAILY",
                        Metrics=["UnblendedCost"],
                    )
                elif perm == "ec2:DescribeInstances":
                    ec2 = self._get_client("ec2")
                    ec2.describe_instances(DryRun=True, MaxResults=1)
                elif perm == "ec2:DescribeRegions":
                    ec2 = self._get_client("ec2")
                    ec2.describe_regions()
                elif perm == "rds:DescribeDBInstances":
                    rds = self._get_client("rds")
                    rds.describe_db_instances(MaxRecords=1)
                elif perm == "lambda:ListFunctions":
                    lambda_client = self._get_client("lambda")
                    lambda_client.list_functions(MaxItems=1)
                elif perm == "s3:ListAllMyBuckets":
                    s3 = self._get_client("s3")
                    s3.list_buckets()
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("AccessDenied", "UnauthorizedOperation"):
                    missing.append(perm)
                # DryRunSuccessful means permission exists
            except Exception:
                # Other errors don't necessarily mean missing permissions
                pass
        return missing

    def get_permission_warnings(self) -> list[str]:
        """Return permission warnings from last credential validation."""
        return self._permission_warnings

    async def get_regions(self) -> list[str]:
        """Get list of enabled AWS regions."""
        try:
            async def _api_call():
                return await asyncio.to_thread(self._get_regions_sync)

            return await with_retry(
                lambda: aws_circuit_breaker.call(_api_call),
                config=AWS_RETRY_CONFIG,
            )
        except ClientError as e:
            logging.getLogger(__name__).warning(f"AWS get_regions error: {_sanitize_csp_error(e)}")
            # Fallback to common regions
            return [
                "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                "eu-west-1", "eu-west-2", "eu-central-1",
                "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
            ]
        except Exception as e:
            logging.getLogger(__name__).warning(f"AWS get_regions error: {_sanitize_csp_error(e)}")
            # Fallback to common regions
            return [
                "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                "eu-west-1", "eu-west-2", "eu-central-1",
                "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
            ]

    def _get_regions_sync(self) -> list[str]:
        """Synchronous region fetching."""
        ec2 = self._get_client("ec2")
        response = ec2.describe_regions(AllRegions=False)
        return [r["RegionName"] for r in response.get("Regions", [])]

    async def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch cost and usage data from AWS Cost Explorer.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: DAILY or MONTHLY
            group_by: List of dimensions to group by (SERVICE, REGION, etc.)

        Returns:
            Cost Explorer response with ResultsByTime
        """
        logger = logging.getLogger(__name__)

        try:
            async def _api_call():
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        self._get_cost_and_usage_sync, start_date, end_date, granularity, group_by
                    ),
                    timeout=25.0
                )

            return await with_retry(
                lambda: aws_circuit_breaker.call(_api_call),
                config=AWS_RETRY_CONFIG,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[DEBUG] AWS Cost Explorer API call timed out after 25s for account {self.account_id or 'unknown'}")
            raise BadRequestError("AWS Cost Explorer API call timed out. The AWS API may be experiencing delays.")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "AccessDeniedException":
                raise BadRequestError(
                    "AWS credentials lack Cost Explorer permissions. "
                    "Ensure the IAM user/role has ce:GetCostAndUsage permission."
                )
            raise BadRequestError(_sanitize_csp_error(e))
        except Exception as e:
            raise BadRequestError(_sanitize_csp_error(e))

    def _get_cost_and_usage_sync(
        self,
        start_date: str,
        end_date: str,
        granularity: str,
        group_by: list[str] | None,
    ) -> dict[str, Any]:
        """Synchronous cost data retrieval."""
        ce = self._get_client("ce", region="us-east-1")  # Cost Explorer is only in us-east-1
        
        params = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": granularity,
            "Metrics": ["UnblendedCost", "UsageQuantity"],
        }
        
        if group_by:
            params["GroupBy"] = [
                {"Type": "DIMENSION", "Key": dim} for dim in group_by
            ]
        
        return ce.get_cost_and_usage(**params)

    async def get_monthly_cost_summary(self) -> dict[str, float]:
        """Get this month and last month cost totals."""
        import logging
        logger = logging.getLogger(__name__)
        
        today = utc_now().date()
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        logger.info(f"[DEBUG] AWSAdapter.get_monthly_cost_summary called for account {self.account_id or 'unknown'}")
        logger.info(f"[DEBUG] Date range: this_month={first_of_month.isoformat()} to {(today + timedelta(days=1)).isoformat()}, last_month={last_month_start.isoformat()} to {first_of_month.isoformat()}")
        
        # This month (up to today)
        logger.info("[DEBUG] Fetching this month data from AWS Cost Explorer")
        this_month_data = await self.get_cost_and_usage(
            start_date=first_of_month.isoformat(),
            end_date=(today + timedelta(days=1)).isoformat(),
            granularity="MONTHLY",
        )
        logger.info(f"[DEBUG] This month raw data: ResultsByTime count={len(this_month_data.get('ResultsByTime', []))}")
        
        # Last month
        logger.info("[DEBUG] Fetching last month data from AWS Cost Explorer")
        last_month_data = await self.get_cost_and_usage(
            start_date=last_month_start.isoformat(),
            end_date=first_of_month.isoformat(),
            granularity="MONTHLY",
        )
        logger.info(f"[DEBUG] Last month raw data: ResultsByTime count={len(last_month_data.get('ResultsByTime', []))}")
        
        this_month_cost = 0.0
        for result in this_month_data.get("ResultsByTime", []):
            amount = float(result.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0))
            logger.info(f"[DEBUG] This month result: {result.get('TimePeriod')} = ${amount}")
            this_month_cost += amount
        
        last_month_cost = 0.0
        for result in last_month_data.get("ResultsByTime", []):
            amount = float(result.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0))
            logger.info(f"[DEBUG] Last month result: {result.get('TimePeriod')} = ${amount}")
            last_month_cost += amount
        
        logger.info(f"[DEBUG] AWS calculated costs: this_month_cost={this_month_cost}, last_month_cost={last_month_cost}")
        
        # Forecast: extrapolate this month
        days_elapsed = max((today - first_of_month).days + 1, 1)
        days_in_month = ((first_of_month + timedelta(days=32)).replace(day=1) - first_of_month).days
        forecast = this_month_cost / days_elapsed * days_in_month
        
        result = {
            "this_month": round(this_month_cost, 2),
            "last_month": round(last_month_cost, 2),
            "forecast": round(forecast, 2),
        }
        logger.info(f"[DEBUG] AWS returning result: {result}")
        return result

    async def get_daily_costs(
        self,
        start_date: str,
        end_date: str,
        group_by: str | None = None,
    ) -> list[dict]:
        """Get daily cost breakdown.
        
        Returns list of {date, cost, [group_key]} dicts.
        """
        group_dims = [group_by.upper()] if group_by else None
        data = await self.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity="DAILY",
            group_by=group_dims,
        )
        
        results = []
        for day_result in data.get("ResultsByTime", []):
            date = day_result["TimePeriod"]["Start"]
            
            if "Groups" in day_result:
                for group in day_result["Groups"]:
                    results.append({
                        "date": date,
                        "cost": round(float(group["Metrics"]["UnblendedCost"]["Amount"]), 2),
                        "group_key": group["Keys"][0] if group["Keys"] else "Unknown",
                    })
            else:
                total = day_result.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0)
                results.append({
                    "date": date,
                    "cost": round(float(total), 2),
                })
        
        return results

    async def discover_resources(self) -> list[dict]:
        """Discover AWS resources across all enabled regions."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[DEBUG] AWS discover_resources starting for account {self.account_id or 'unknown'}")
        resources = []
        regions = await self.get_regions()
        logger.info(f"[DEBUG] AWS will discover resources in {len(regions)} regions")
        
        # Use semaphore to limit concurrent region discovery
        semaphore = asyncio.Semaphore(5)
        
        async def discover_region(region: str):
            async with semaphore:
                region_resources = []
                try:
                    # EC2 Instances
                    ec2_resources = await self._discover_ec2_instances(region)
                    logger.debug(f"[DEBUG] AWS region {region}: found {len(ec2_resources)} EC2 instances")
                    region_resources.extend(ec2_resources)
                    # RDS Instances
                    rds_resources = await self._discover_rds_instances(region)
                    logger.debug(f"[DEBUG] AWS region {region}: found {len(rds_resources)} RDS instances")
                    region_resources.extend(rds_resources)
                    # Lambda Functions
                    lambda_resources = await self._discover_lambda_functions(region)
                    logger.debug(f"[DEBUG] AWS region {region}: found {len(lambda_resources)} Lambda functions")
                    region_resources.extend(lambda_resources)
                except Exception as e:
                    logger.error(f"[DEBUG] AWS region {region} discovery failed: {type(e).__name__}: {e}")
                return region_resources
        
        # Discover resources in all regions concurrently
        tasks = [discover_region(region) for region in regions]
        region_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in region_results:
            if isinstance(result, list):
                resources.extend(result)
        
        # S3 Buckets (global service, query once)
        s3_resources = await self._discover_s3_buckets()
        logger.info(f"[DEBUG] AWS discovered {len(s3_resources)} S3 buckets")
        resources.extend(s3_resources)
        
        logger.info(f"[DEBUG] AWS discover_resources completed: total {len(resources)} resources")
        return resources

    async def _discover_ec2_instances(self, region: str) -> list[dict]:
        """Discover EC2 instances in a region."""
        try:
            async def _api_call():
                return await asyncio.to_thread(self._discover_ec2_instances_sync, region)

            return await with_retry(
                lambda: aws_circuit_breaker.call(_api_call),
                config=AWS_RETRY_CONFIG,
            )
        except ClientError as e:
            logging.getLogger(__name__).debug(f"AWS EC2 discovery error: {_sanitize_csp_error(e)}")
            return []
        except Exception:
            return []

    def _discover_ec2_instances_sync(self, region: str) -> list[dict]:
        """Synchronous EC2 discovery."""
        resources = []
        ec2 = self._get_client("ec2", region)
        paginator = ec2.get_paginator("describe_instances")
        
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    name = ""
                    tags = {}
                    for tag in instance.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                    
                    resources.append({
                        "cloud_resource_id": instance["InstanceId"],
                        "name": name or instance["InstanceId"],
                        "resource_type": "EC2 Instance",
                        "region": region,
                        "state": instance["State"]["Name"],
                        "instance_type": instance.get("InstanceType", ""),
                        "launch_time": instance.get("LaunchTime").isoformat() if instance.get("LaunchTime") else None,
                        "tags": tags,
                        "meta": {
                            "instance_type": instance.get("InstanceType", ""),
                            "platform": instance.get("Platform", "Linux"),
                            "vpc_id": instance.get("VpcId", ""),
                            "subnet_id": instance.get("SubnetId", ""),
                            "private_ip": instance.get("PrivateIpAddress", ""),
                            "public_ip": instance.get("PublicIpAddress", ""),
                        },
                    })
        return resources

    async def _discover_rds_instances(self, region: str) -> list[dict]:
        """Discover RDS instances in a region."""
        try:
            async def _api_call():
                return await asyncio.to_thread(self._discover_rds_instances_sync, region)

            return await with_retry(
                lambda: aws_circuit_breaker.call(_api_call),
                config=AWS_RETRY_CONFIG,
            )
        except ClientError as e:
            logging.getLogger(__name__).debug(f"AWS RDS discovery error: {_sanitize_csp_error(e)}")
            return []
        except Exception:
            return []

    def _discover_rds_instances_sync(self, region: str) -> list[dict]:
        """Synchronous RDS discovery."""
        resources = []
        rds = self._get_client("rds", region)
        paginator = rds.get_paginator("describe_db_instances")
        
        for page in paginator.paginate():
            for db in page.get("DBInstances", []):
                tags = {t["Key"]: t["Value"] for t in db.get("TagList", [])}
                
                resources.append({
                    "cloud_resource_id": db["DBInstanceArn"],
                    "name": db["DBInstanceIdentifier"],
                    "resource_type": "RDS Instance",
                    "region": region,
                    "state": db["DBInstanceStatus"],
                    "tags": tags,
                    "meta": {
                        "engine": db.get("Engine", ""),
                        "engine_version": db.get("EngineVersion", ""),
                        "instance_class": db.get("DBInstanceClass", ""),
                        "storage_gb": db.get("AllocatedStorage", 0),
                        "multi_az": db.get("MultiAZ", False),
                        "endpoint": db.get("Endpoint", {}).get("Address", ""),
                    },
                })
        return resources

    async def _discover_s3_buckets(self) -> list[dict]:
        """Discover S3 buckets (global service)."""
        try:
            async def _api_call():
                return await asyncio.to_thread(self._discover_s3_buckets_sync)

            return await with_retry(
                lambda: aws_circuit_breaker.call(_api_call),
                config=AWS_RETRY_CONFIG,
            )
        except ClientError as e:
            logging.getLogger(__name__).debug(f"AWS S3 discovery error: {_sanitize_csp_error(e)}")
            return []
        except Exception:
            return []

    def _discover_s3_buckets_sync(self) -> list[dict]:
        """Synchronous S3 discovery."""
        resources = []
        s3 = self._get_client("s3")
        response = s3.list_buckets()
        
        for bucket in response.get("Buckets", []):
            bucket_name = bucket["Name"]
            
            # Get bucket location
            try:
                loc_response = s3.get_bucket_location(Bucket=bucket_name)
                region = loc_response.get("LocationConstraint") or "us-east-1"
            except ClientError:
                region = "unknown"
            
            # Get bucket tags
            tags = {}
            try:
                tag_response = s3.get_bucket_tagging(Bucket=bucket_name)
                tags = {t["Key"]: t["Value"] for t in tag_response.get("TagSet", [])}
            except ClientError:
                pass  # No tags or no permission
            
            resources.append({
                "cloud_resource_id": f"arn:aws:s3:::{bucket_name}",
                "name": bucket_name,
                "resource_type": "S3 Bucket",
                "region": region,
                "state": "available",
                "tags": tags,
                "meta": {
                    "creation_date": bucket.get("CreationDate").isoformat() if bucket.get("CreationDate") else None,
                },
            })
        return resources

    async def _discover_lambda_functions(self, region: str) -> list[dict]:
        """Discover Lambda functions in a region."""
        try:
            async def _api_call():
                return await asyncio.to_thread(self._discover_lambda_functions_sync, region)

            return await with_retry(
                lambda: aws_circuit_breaker.call(_api_call),
                config=AWS_RETRY_CONFIG,
            )
        except ClientError as e:
            logging.getLogger(__name__).debug(f"AWS Lambda discovery error: {_sanitize_csp_error(e)}")
            return []
        except Exception:
            return []

    def _discover_lambda_functions_sync(self, region: str) -> list[dict]:
        """Synchronous Lambda discovery."""
        resources = []
        lambda_client = self._get_client("lambda", region)
        paginator = lambda_client.get_paginator("list_functions")
        
        for page in paginator.paginate():
            for func in page.get("Functions", []):
                # Get tags
                tags = {}
                try:
                    tag_response = lambda_client.list_tags(Resource=func["FunctionArn"])
                    tags = tag_response.get("Tags", {})
                except ClientError:
                    pass
                
                resources.append({
                    "cloud_resource_id": func["FunctionArn"],
                    "name": func["FunctionName"],
                    "resource_type": "Lambda Function",
                    "region": region,
                    "state": "active",
                    "tags": tags,
                    "meta": {
                        "runtime": func.get("Runtime", ""),
                        "memory_mb": func.get("MemorySize", 0),
                        "timeout_seconds": func.get("Timeout", 0),
                        "handler": func.get("Handler", ""),
                        "last_modified": func.get("LastModified", ""),
                    },
                })
        return resources

    async def get_resource_cost(self, resource_id: str, days: int = 30) -> dict:
        """Get cost for a specific resource over the past N days.
        
        Note: AWS Cost Explorer can filter by resource ID for some services
        but this requires specific tagging. This is a simplified version.
        """
        end_date = utc_now().date()
        start_date = end_date - timedelta(days=days)
        
        # This requires the resource to be tagged or Cost Allocation Tags enabled
        # For now, return a placeholder - full implementation needs resource tagging
        return {
            "resource_id": resource_id,
            "total_cost": 0.0,
            "daily_costs": [],
            "note": "Per-resource costs require Cost Allocation Tags to be enabled in AWS",
        }
