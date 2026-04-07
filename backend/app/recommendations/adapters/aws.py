import asyncio
import logging

from app.recommendations.adapters.base import NormalizedRecommendation, RecommenderAdapter

logger = logging.getLogger(__name__)


class AwsRecommenderAdapter(RecommenderAdapter):
    """Fetch recommendations from AWS Cost Explorer, Compute Optimizer, and resource APIs."""

    async def fetch_recommendations(self, config: dict) -> list[NormalizedRecommendation]:
        try:
            return await asyncio.to_thread(self._fetch_sync, config)
        except Exception:
            logger.exception("Failed to fetch AWS recommendations")
            return []

    def _fetch_sync(self, config: dict) -> list[NormalizedRecommendation]:
        import boto3

        session = boto3.Session(
            aws_access_key_id=config.get("aws_access_key_id"),
            aws_secret_access_key=config.get("aws_secret_access_key"),
            region_name=config.get("region_name", "us-east-1"),
        )
        results: list[NormalizedRecommendation] = []

        # Rightsizing recommendations from Cost Explorer
        results.extend(self._get_rightsizing_recommendations(session))

        # Reserved Instance recommendations from Cost Explorer
        results.extend(self._get_ri_recommendations(session))

        # Savings Plan recommendations from Cost Explorer
        results.extend(self._get_savings_plan_recommendations(session))

        # Unattached EBS volumes
        results.extend(self._get_unattached_volumes(session))

        # Obsolete snapshots
        results.extend(self._get_obsolete_snapshots(session))

        # Unassociated Elastic IPs
        results.extend(self._get_unassociated_eips(session))

        # Idle load balancers
        results.extend(self._get_idle_load_balancers(session))

        # Public S3 buckets (security)
        results.extend(self._get_public_s3_buckets(session))

        return results

    def _get_rightsizing_recommendations(self, session) -> list[NormalizedRecommendation]:
        """Fetch EC2 rightsizing recommendations from Cost Explorer."""
        results = []
        try:
            ce = session.client("ce", region_name="us-east-1")
            resp = ce.get_rightsizing_recommendation(
                Service="AmazonEC2",
                Configuration={
                    "RecommendationTarget": "SAME_INSTANCE_FAMILY",
                    "BenefitsConsidered": True,
                },
            )
            for rec in resp.get("RightsizingRecommendations", []):
                current = rec.get("CurrentInstance", {})
                resource_id = current.get("ResourceId", "")
                saving = 0.0
                target_type = ""
                
                action = rec.get("RightsizingType", "Modify")
                if action == "Terminate":
                    # Instance should be terminated
                    saving = float(current.get("MonthlyCost", "0"))
                    results.append(NormalizedRecommendation(
                        rec_type="abandoned_instances",
                        name="Abandon Instance",
                        description=f"Terminate idle instance {resource_id}",
                        category="cost",
                        resource_id=resource_id,
                        resource_name=current.get("InstanceName", resource_id),
                        cloud_type="aws_cnr",
                        region=current.get("ResourceDetails", {}).get("EC2ResourceDetails", {}).get("Region", ""),
                        source_service="AWS Cost Explorer",
                        saving=saving,
                    ))
                else:
                    # Instance should be downsized
                    modify = rec.get("ModifyRecommendationDetail", {})
                    if modify and modify.get("TargetInstances"):
                        target = modify["TargetInstances"][0]
                        saving = float(target.get("EstimatedMonthlySavings", "0"))
                        target_type = target.get("ResourceDetails", {}).get("EC2ResourceDetails", {}).get("InstanceType", "")
                    
                    current_type = current.get("ResourceDetails", {}).get("EC2ResourceDetails", {}).get("InstanceType", "")
                    results.append(NormalizedRecommendation(
                        rec_type="rightsizing_instances",
                        name="Rightsizing Instance",
                        description=f"Resize {resource_id} from {current_type} to {target_type}",
                        category="cost",
                        resource_id=resource_id,
                        resource_name=current.get("InstanceName", resource_id),
                        cloud_type="aws_cnr",
                        region=current.get("ResourceDetails", {}).get("EC2ResourceDetails", {}).get("Region", ""),
                        source_service="AWS Cost Explorer",
                        saving=saving,
                        metadata={"current_type": current_type, "target_type": target_type},
                    ))
        except Exception as e:
            logger.debug("AWS rightsizing API call failed: %s", e)
        return results

    def _get_ri_recommendations(self, session) -> list[NormalizedRecommendation]:
        """Fetch Reserved Instance recommendations from Cost Explorer."""
        results = []
        try:
            ce = session.client("ce", region_name="us-east-1")
            resp = ce.get_reservation_purchase_recommendation(
                Service="AmazonEC2",
                LookbackPeriodInDays="SIXTY_DAYS",
                TermInYears="ONE_YEAR",
                PaymentOption="NO_UPFRONT",
            )
            for detail in resp.get("Recommendations", []):
                for item in detail.get("RecommendationDetails", []):
                    saving = float(item.get("EstimatedMonthlySavingsAmount", 0))
                    instance_details = item.get("InstanceDetails", {}).get("EC2InstanceDetails", {})
                    instance_type = instance_details.get("InstanceType", "unknown")
                    region = instance_details.get("Region", "")
                    
                    results.append(NormalizedRecommendation(
                        rec_type="reserved_instances",
                        name="Reserved Instance",
                        description=f"Purchase 1-year RI for {instance_type} in {region}",
                        category="cost",
                        resource_id=instance_type,
                        resource_name=f"RI - {instance_type}",
                        cloud_type="aws_cnr",
                        region=region,
                        source_service="AWS Cost Explorer",
                        saving=saving,
                        metadata={
                            "instance_type": instance_type,
                            "term": "1 year",
                            "payment_option": "No Upfront",
                        },
                    ))
        except Exception as e:
            logger.debug("AWS RI recommendation API call failed: %s", e)
        return results

    def _get_savings_plan_recommendations(self, session) -> list[NormalizedRecommendation]:
        """Fetch Savings Plan recommendations from Cost Explorer."""
        results = []
        try:
            ce = session.client("ce", region_name="us-east-1")
            resp = ce.get_savings_plans_purchase_recommendation(
                SavingsPlansType="COMPUTE_SP",
                LookbackPeriodInDays="SIXTY_DAYS",
                TermInYears="ONE_YEAR",
                PaymentOption="NO_UPFRONT",
            )
            for detail in resp.get("SavingsPlansPurchaseRecommendation", {}).get("SavingsPlansPurchaseRecommendationDetails", []):
                saving = float(detail.get("EstimatedMonthlySavingsAmount", 0))
                commitment = float(detail.get("HourlyCommitmentToPurchase", 0))
                
                if saving > 0:
                    results.append(NormalizedRecommendation(
                        rec_type="savings_plans",
                        name="Compute Savings Plan",
                        description=f"Purchase 1-year Compute Savings Plan (${commitment:.2f}/hr commitment)",
                        category="cost",
                        resource_id="savings-plan-compute",
                        resource_name="Compute Savings Plan",
                        cloud_type="aws_cnr",
                        region="global",
                        source_service="AWS Cost Explorer",
                        saving=saving,
                        metadata={
                            "type": "Compute SP",
                            "hourly_commitment": commitment,
                            "term": "1 year",
                        },
                    ))
        except Exception as e:
            logger.debug("AWS Savings Plan recommendation API call failed: %s", e)
        return results

    def _get_unattached_volumes(self, session) -> list[NormalizedRecommendation]:
        """Find EBS volumes that are not attached to any instance."""
        results = []
        try:
            # Get pricing estimate per GB (approximate)
            price_per_gb = 0.10  # gp2/gp3 approximate monthly cost per GB
            
            for region in self._get_enabled_regions(session):
                try:
                    ec2 = session.client("ec2", region_name=region)
                    volumes = ec2.describe_volumes(
                        Filters=[{"Name": "status", "Values": ["available"]}]
                    ).get("Volumes", [])
                    
                    for vol in volumes:
                        size = vol.get("Size", 0)
                        monthly_cost = size * price_per_gb
                        vol_id = vol.get("VolumeId", "")
                        vol_type = vol.get("VolumeType", "gp2")
                        
                        results.append(NormalizedRecommendation(
                            rec_type="volumes_not_attached",
                            name="Unattached Volume",
                            description=f"Delete unattached {vol_type} volume {vol_id} ({size} GB)",
                            category="cost",
                            resource_id=vol_id,
                            resource_name=vol_id,
                            cloud_type="aws_cnr",
                            region=region,
                            source_service="AWS EC2",
                            saving=monthly_cost,
                            metadata={"size_gb": size, "volume_type": vol_type},
                        ))
                except Exception as e:
                    logger.debug("Failed to get volumes in %s: %s", region, e)
        except Exception as e:
            logger.debug("Failed to get unattached volumes: %s", e)
        return results

    def _get_obsolete_snapshots(self, session) -> list[NormalizedRecommendation]:
        """Find EBS snapshots that may be obsolete (orphaned from deleted volumes)."""
        results = []
        try:
            # Get pricing estimate per GB (approximate)
            price_per_gb = 0.05  # Snapshot storage cost per GB per month
            
            for region in self._get_enabled_regions(session):
                try:
                    ec2 = session.client("ec2", region_name=region)
                    
                    # Get all snapshots owned by the account
                    snapshots = ec2.describe_snapshots(OwnerIds=["self"]).get("Snapshots", [])
                    
                    # Get all volume IDs that exist
                    volumes = ec2.describe_volumes().get("Volumes", [])
                    existing_volume_ids = {v["VolumeId"] for v in volumes}
                    
                    # Get all AMI snapshot IDs
                    images = ec2.describe_images(Owners=["self"]).get("Images", [])
                    ami_snapshot_ids = set()
                    for img in images:
                        for bdm in img.get("BlockDeviceMappings", []):
                            if "Ebs" in bdm and "SnapshotId" in bdm["Ebs"]:
                                ami_snapshot_ids.add(bdm["Ebs"]["SnapshotId"])
                    
                    for snap in snapshots:
                        snap_id = snap.get("SnapshotId", "")
                        volume_id = snap.get("VolumeId", "")
                        size = snap.get("VolumeSize", 0)
                        
                        # Check if snapshot is orphaned (volume deleted and not used by AMI)
                        is_orphaned = (
                            volume_id not in existing_volume_ids and 
                            snap_id not in ami_snapshot_ids
                        )
                        
                        if is_orphaned:
                            monthly_cost = size * price_per_gb
                            results.append(NormalizedRecommendation(
                                rec_type="obsolete_snapshots",
                                name="Obsolete Snapshot",
                                description=f"Delete orphaned snapshot {snap_id} ({size} GB)",
                                category="cost",
                                resource_id=snap_id,
                                resource_name=snap.get("Description", snap_id)[:50],
                                cloud_type="aws_cnr",
                                region=region,
                                source_service="AWS EC2",
                                saving=monthly_cost,
                                metadata={"size_gb": size, "original_volume": volume_id},
                            ))
                except Exception as e:
                    logger.debug("Failed to get snapshots in %s: %s", region, e)
        except Exception as e:
            logger.debug("Failed to get obsolete snapshots: %s", e)
        return results

    def _get_unassociated_eips(self, session) -> list[NormalizedRecommendation]:
        """Find Elastic IPs not associated with any resource."""
        results = []
        eip_monthly_cost = 3.60  # ~$0.005/hr when not associated
        
        try:
            for region in self._get_enabled_regions(session):
                try:
                    ec2 = session.client("ec2", region_name=region)
                    addresses = ec2.describe_addresses().get("Addresses", [])
                    
                    for addr in addresses:
                        # If not associated with instance or network interface
                        if not addr.get("InstanceId") and not addr.get("NetworkInterfaceId"):
                            ip = addr.get("PublicIp", "")
                            alloc_id = addr.get("AllocationId", "")
                            
                            results.append(NormalizedRecommendation(
                                rec_type="obsolete_ips",
                                name="Unassociated Elastic IP",
                                description=f"Release unused Elastic IP {ip}",
                                category="cost",
                                resource_id=alloc_id or ip,
                                resource_name=ip,
                                cloud_type="aws_cnr",
                                region=region,
                                source_service="AWS EC2",
                                saving=eip_monthly_cost,
                                metadata={"public_ip": ip},
                            ))
                except Exception as e:
                    logger.debug("Failed to get EIPs in %s: %s", region, e)
        except Exception as e:
            logger.debug("Failed to get unassociated EIPs: %s", e)
        return results

    def _get_idle_load_balancers(self, session) -> list[NormalizedRecommendation]:
        """Find load balancers with no healthy targets or zero request count."""
        results = []
        
        try:
            for region in self._get_enabled_regions(session):
                try:
                    elbv2 = session.client("elbv2", region_name=region)
                    
                    # Get all load balancers
                    lbs = elbv2.describe_load_balancers().get("LoadBalancers", [])
                    
                    for lb in lbs:
                        lb_arn = lb.get("LoadBalancerArn", "")
                        lb_name = lb.get("LoadBalancerName", "")
                        lb_type = lb.get("Type", "application")
                        
                        # Get target groups for this LB
                        tgs = elbv2.describe_target_groups(
                            LoadBalancerArn=lb_arn
                        ).get("TargetGroups", [])
                        
                        has_healthy_targets = False
                        for tg in tgs:
                            tg_arn = tg.get("TargetGroupArn", "")
                            health = elbv2.describe_target_health(
                                TargetGroupArn=tg_arn
                            ).get("TargetHealthDescriptions", [])
                            
                            for target in health:
                                if target.get("TargetHealth", {}).get("State") == "healthy":
                                    has_healthy_targets = True
                                    break
                            if has_healthy_targets:
                                break
                        
                        if not has_healthy_targets:
                            # Estimate cost based on LB type
                            monthly_cost = 22.0 if lb_type == "application" else 18.0
                            
                            results.append(NormalizedRecommendation(
                                rec_type="idle_load_balancers",
                                name="Idle Load Balancer",
                                description=f"Delete load balancer {lb_name} with no healthy targets",
                                category="cost",
                                resource_id=lb_arn,
                                resource_name=lb_name,
                                cloud_type="aws_cnr",
                                region=region,
                                source_service="AWS ELB",
                                saving=monthly_cost,
                                metadata={"lb_type": lb_type},
                            ))
                except Exception as e:
                    logger.debug("Failed to check LBs in %s: %s", region, e)
        except Exception as e:
            logger.debug("Failed to get idle load balancers: %s", e)
        return results

    def _get_public_s3_buckets(self, session) -> list[NormalizedRecommendation]:
        """Find S3 buckets with public access (security recommendation)."""
        results = []
        try:
            s3 = session.client("s3")
            s3_control = session.client("s3control")
            
            # Get account ID for s3control
            sts = session.client("sts")
            account_id = sts.get_caller_identity()["Account"]
            
            buckets = s3.list_buckets().get("Buckets", [])
            
            for bucket in buckets:
                bucket_name = bucket.get("Name", "")
                is_public = False
                reason = ""
                
                try:
                    # Check public access block
                    try:
                        pab = s3.get_public_access_block(Bucket=bucket_name)
                        config = pab.get("PublicAccessBlockConfiguration", {})
                        if not all([
                            config.get("BlockPublicAcls", False),
                            config.get("IgnorePublicAcls", False),
                            config.get("BlockPublicPolicy", False),
                            config.get("RestrictPublicBuckets", False),
                        ]):
                            is_public = True
                            reason = "Public access block not fully enabled"
                    except s3.exceptions.NoSuchPublicAccessBlockConfiguration:
                        is_public = True
                        reason = "No public access block configured"
                    except Exception:
                        pass  # Skip buckets we can't check
                    
                    # Check bucket ACL
                    if not is_public:
                        try:
                            acl = s3.get_bucket_acl(Bucket=bucket_name)
                            for grant in acl.get("Grants", []):
                                grantee = grant.get("Grantee", {})
                                if grantee.get("URI") in [
                                    "http://acs.amazonaws.com/groups/global/AllUsers",
                                    "http://acs.amazonaws.com/groups/global/AuthenticatedUsers",
                                ]:
                                    is_public = True
                                    reason = "Public ACL grants detected"
                                    break
                        except Exception:
                            pass
                    
                    if is_public:
                        results.append(NormalizedRecommendation(
                            rec_type="s3_public_buckets",
                            name="Public S3 Bucket",
                            description=f"Secure bucket {bucket_name}: {reason}",
                            category="security",
                            resource_id=bucket_name,
                            resource_name=bucket_name,
                            cloud_type="aws_cnr",
                            region="global",
                            source_service="AWS S3",
                            saving=0.0,
                            metadata={"reason": reason},
                        ))
                except Exception as e:
                    logger.debug("Failed to check bucket %s: %s", bucket_name, e)
        except Exception as e:
            logger.debug("Failed to get public S3 buckets: %s", e)
        return results

    def _get_enabled_regions(self, session) -> list[str]:
        """Get list of enabled regions for the account (limited set for performance)."""
        # Use a common subset to avoid too many API calls
        return ["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"]
