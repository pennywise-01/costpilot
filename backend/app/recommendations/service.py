import hashlib
import random
import time
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.recommendations.schemas import RecommendationType, RecommendationsOverview, WellArchitectedRule

# ---------------------------------------------------------------------------
# All 25 recommendation type definitions (23 cost + 2 security)
# ---------------------------------------------------------------------------

_RECOMMENDATION_DEFS: list[dict] = [
    # ---- cost category ----
    {
        "type": "abandoned_instances",
        "name": "Abandoned Instances",
        "description": "Instances that have been running with low CPU utilisation for an extended period and can likely be terminated.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 5,
        "demo_saving": 450.00,
    },
    {
        "type": "volumes_not_attached",
        "name": "Volumes Not Attached",
        "description": "EBS / disk volumes that are not attached to any running instance.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr"],
        "demo_count": 12,
        "demo_saving": 185.50,
    },
    {
        "type": "obsolete_snapshots",
        "name": "Obsolete Snapshots",
        "description": "Snapshots older than the configured retention period with no dependent AMI / image.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr"],
        "demo_count": 18,
        "demo_saving": 92.30,
    },
    {
        "type": "instances_for_shutdown",
        "name": "Instances for Shutdown",
        "description": "Instances that are only used during business hours and can be scheduled for shutdown outside those hours.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 6,
        "demo_saving": 380.00,
    },
    {
        "type": "rightsizing_instances",
        "name": "Rightsizing Instances",
        "description": "Instances that are over-provisioned based on CPU and memory metrics and can be downsized.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 8,
        "demo_saving": 320.75,
    },
    {
        "type": "reserved_instances",
        "name": "Reserved Instances",
        "description": "On-demand instances that would benefit from reserved instance or savings plan commitments.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr"],
        "demo_count": 4,
        "demo_saving": 620.00,
    },
    {
        "type": "s3_abandoned_buckets",
        "name": "Abandoned S3 Buckets",
        "description": "S3 buckets with no recent access that are accumulating storage costs.",
        "category": "cost",
        "cloud_types": ["aws_cnr"],
        "demo_count": 3,
        "demo_saving": 45.20,
    },
    {
        "type": "obsolete_ips",
        "name": "Obsolete IP Addresses",
        "description": "Elastic / static IP addresses that are allocated but not associated with any running resource.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 7,
        "demo_saving": 25.20,
    },
    {
        "type": "instance_generation_upgrade",
        "name": "Instance Generation Upgrade",
        "description": "Instances running on previous-generation hardware that can be migrated to newer, cheaper generations.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr"],
        "demo_count": 3,
        "demo_saving": 115.00,
    },
    {
        "type": "short_living_instances",
        "name": "Short Living Instances",
        "description": "Instances that are repeatedly launched and terminated within a short window, suggesting spot / preemptible usage opportunities.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "gcp_cnr"],
        "demo_count": 4,
        "demo_saving": 78.50,
    },
    {
        "type": "abandoned_load_balancers",
        "name": "Abandoned Load Balancers",
        "description": "Load balancers with no healthy backend targets or zero traffic over the past 14 days.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 2,
        "demo_saving": 62.00,
    },
    {
        "type": "abandoned_images",
        "name": "Abandoned Images",
        "description": "Machine images (AMIs / custom images) that have not been used to launch any instance in over 90 days.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 9,
        "demo_saving": 33.80,
    },
    {
        "type": "s3_intelligent_tiering",
        "name": "S3 Intelligent Tiering",
        "description": "S3 buckets with infrequent access patterns that would save money using Intelligent-Tiering storage class.",
        "category": "cost",
        "cloud_types": ["aws_cnr"],
        "demo_count": 5,
        "demo_saving": 58.40,
    },
    {
        "type": "abandoned_kinesis_streams",
        "name": "Abandoned Kinesis Streams",
        "description": "Kinesis data streams with no incoming records or consumer activity.",
        "category": "cost",
        "cloud_types": ["aws_cnr"],
        "demo_count": 1,
        "demo_saving": 42.00,
    },
    {
        "type": "inactive_users",
        "name": "Inactive IAM Users",
        "description": "IAM users who have not performed any API activity in over 90 days.",
        "category": "cost",
        "cloud_types": ["aws_cnr"],
        "demo_count": 6,
        "demo_saving": 0.00,
    },
    {
        "type": "inactive_console_users",
        "name": "Inactive Console Users",
        "description": "IAM users who have not signed in to the console in over 90 days.",
        "category": "cost",
        "cloud_types": ["aws_cnr"],
        "demo_count": 4,
        "demo_saving": 0.00,
    },
    {
        "type": "instances_in_stopped_state",
        "name": "Instances in Stopped State",
        "description": "Instances that have been in a stopped state for more than 7 days and still incur storage costs.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 3,
        "demo_saving": 28.90,
    },
    {
        "type": "obsolete_snapshot_chains",
        "name": "Obsolete Snapshot Chains",
        "description": "Chains of incremental snapshots where the parent volume has been deleted.",
        "category": "cost",
        "cloud_types": ["aws_cnr"],
        "demo_count": 7,
        "demo_saving": 41.60,
    },
    {
        "type": "rightsizing_rds",
        "name": "Rightsizing RDS Instances",
        "description": "RDS instances that are over-provisioned based on CPU, memory, and connection metrics.",
        "category": "cost",
        "cloud_types": ["aws_cnr"],
        "demo_count": 2,
        "demo_saving": 155.00,
    },
    {
        "type": "instance_subscription",
        "name": "Instance Subscription",
        "description": "On-demand instances that would benefit from subscription-based pricing (Azure Reserved VM Instances, GCP CUDs).",
        "category": "cost",
        "cloud_types": ["azure_cnr", "gcp_cnr"],
        "demo_count": 3,
        "demo_saving": 210.00,
    },
    {
        "type": "cvos_opportunities",
        "name": "Cross-cloud Volume Optimisation",
        "description": "Workloads that can be migrated across clouds to take advantage of volume discounts.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 2,
        "demo_saving": 175.00,
    },
    {
        "type": "nebius_migration",
        "name": "Nebius Migration",
        "description": "GPU workloads that could be migrated to Nebius for significant cost reduction.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 1,
        "demo_saving": 340.00,
    },
    {
        "type": "instance_migration",
        "name": "Instance Migration",
        "description": "Instances that would be cheaper on a different cloud provider based on current pricing.",
        "category": "cost",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 4,
        "demo_saving": 290.00,
    },
    # ---- security category ----
    {
        "type": "insecure_security_groups",
        "name": "Insecure Security Groups",
        "description": "Security groups with overly permissive rules (e.g. 0.0.0.0/0 on sensitive ports).",
        "category": "security",
        "cloud_types": ["aws_cnr", "azure_cnr", "gcp_cnr"],
        "demo_count": 6,
        "demo_saving": 0.00,
    },
    {
        "type": "s3_public_buckets",
        "name": "Public S3 Buckets",
        "description": "S3 / Blob Storage containers that are publicly accessible and may expose sensitive data.",
        "category": "security",
        "cloud_types": ["aws_cnr", "azure_cnr"],
        "demo_count": 2,
        "demo_saving": 0.00,
    },
]


# ---------------------------------------------------------------------------
# Well-Architected Framework rules mapped to each recommendation type
# ---------------------------------------------------------------------------

_WELL_ARCHITECTED_RULES: dict[str, list[dict]] = {
    "abandoned_instances": [
        {
            "id": "aws-co-01",
            "title": "Terminate idle instances with <2% average CPU over 14 days",
            "description": "Identify EC2 instances with sustained low CPU utilisation (<2% average) over a 14-day period. These instances are likely abandoned and should be terminated to eliminate waste.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-01",
            "title": "Deallocate VMs with no network or disk activity for 7+ days",
            "description": "Azure VMs that show zero network bytes in/out and minimal disk operations for 7 consecutive days should be deallocated. Stopped-but-allocated VMs still incur compute charges.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 100,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-01",
            "title": "Delete idle Compute Engine VMs with zero requests for 14 days",
            "description": "GCP Compute Engine instances with negligible CPU usage and no inbound requests for 14 days should be deleted. Use recommender API idle VM insights to automate detection.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 100,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/monitor",
        },
    ],
    "volumes_not_attached": [
        {
            "id": "aws-co-02",
            "title": "Delete unattached EBS volumes after snapshot backup",
            "description": "EBS volumes not attached to any instance for 30+ days accumulate storage costs with no value. Create a snapshot for backup if needed, then delete the volume.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-02",
            "title": "Remove unattached managed disks",
            "description": "Azure managed disks in 'Unattached' state continue to incur charges. Review and delete disks not associated with any VM, keeping snapshots as needed.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 100,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
    ],
    "obsolete_snapshots": [
        {
            "id": "aws-co-03",
            "title": "Delete snapshots with no associated AMI or volume older than retention period",
            "description": "EBS snapshots whose parent volume has been deleted and that are not referenced by any AMI should be removed after the retention period expires. Use lifecycle policies to automate.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-03",
            "title": "Purge orphaned Azure snapshots older than 90 days",
            "description": "Snapshots of deleted managed disks remain billable. Implement an automated cleanup policy to remove snapshots older than 90 days that have no dependent image.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
    ],
    "instances_for_shutdown": [
        {
            "id": "aws-co-04",
            "title": "Schedule non-production instances to stop outside business hours",
            "description": "Use AWS Instance Scheduler or EventBridge rules to automatically stop dev/test instances outside business hours (nights and weekends). Typical saving is 65% of on-demand cost.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 65,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-04",
            "title": "Auto-shutdown dev/test VMs with Azure DevTest Labs or Automation",
            "description": "Configure auto-shutdown schedules for non-production VMs using Azure DevTest Labs or Azure Automation runbooks. Deallocated VMs incur no compute charges.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 65,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-04",
            "title": "Use instance schedules for non-production Compute Engine VMs",
            "description": "Create Compute Engine instance schedules to automatically stop and start dev/test VMs based on a cron schedule. Saves up to 65% compared to 24/7 running.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 65,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/optimize-compute",
        },
    ],
    "rightsizing_instances": [
        {
            "id": "aws-co-05",
            "title": "Downsize over-provisioned EC2 instances based on CloudWatch metrics",
            "description": "Instances with <40% average CPU and <60% memory utilisation are over-provisioned. Use AWS Compute Optimizer recommendations to select a smaller instance family. Typical savings of 20-50%.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 35,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
        {
            "id": "azure-co-05",
            "title": "Resize over-provisioned VMs using Azure Advisor recommendations",
            "description": "Azure Advisor identifies VMs with <5% average CPU. Resize to a smaller SKU or B-series burstable instances for intermittent workloads. Expected savings of 25-50%.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 35,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-05",
            "title": "Apply Recommender API rightsizing suggestions for Compute Engine",
            "description": "GCP Recommender API provides machine type recommendations based on historical CPU and memory utilisation. Switching to recommended types typically saves 25-40%.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 35,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/optimize-compute",
        },
    ],
    "reserved_instances": [
        {
            "id": "aws-co-06",
            "title": "Purchase Reserved Instances or Savings Plans for steady-state workloads",
            "description": "On-demand instances running 24/7 for 3+ months should use 1-year or 3-year Reserved Instances or Compute Savings Plans. Savings of 30-60% compared to on-demand pricing.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "critical",
            "estimated_saving_pct": 40,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
        {
            "id": "azure-co-06",
            "title": "Commit to Azure Reserved VM Instances for predictable workloads",
            "description": "Azure Reserved VM Instances offer up to 72% discount compared to pay-as-you-go pricing for 1- or 3-year commitments on consistent workloads.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "critical",
            "estimated_saving_pct": 40,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
    ],
    "s3_abandoned_buckets": [
        {
            "id": "aws-co-07",
            "title": "Delete or archive S3 buckets with no access for 90+ days",
            "description": "S3 buckets with no GET/PUT requests for 90 days accumulate unnecessary storage costs. Archive contents to S3 Glacier Deep Archive or delete if no longer needed.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 90,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
    ],
    "obsolete_ips": [
        {
            "id": "aws-co-08",
            "title": "Release unassociated Elastic IP addresses",
            "description": "AWS charges for Elastic IPs not associated with a running instance. Release any EIPs that have been unassociated for more than 7 days.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-08",
            "title": "Delete unattached Azure Public IP addresses",
            "description": "Standard SKU public IPs incur hourly charges even when unattached. Remove public IPs not associated with any NIC, load balancer, or gateway.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-08",
            "title": "Release unattached GCP static external IP addresses",
            "description": "GCP charges for static external IPs that are reserved but not in use. Release any that have been unattached for more than 7 days.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/monitor",
        },
    ],
    "instance_generation_upgrade": [
        {
            "id": "aws-co-09",
            "title": "Migrate previous-gen EC2 instances to current generation",
            "description": "Previous-generation instance families (M4, C4, R4, etc.) cost more per vCPU/GB than current generation (M6i, C6i, R6i). Migrating typically saves 10-20% with better performance.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 15,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
        {
            "id": "azure-co-09",
            "title": "Upgrade to latest Azure VM series (Dv5/Ev5)",
            "description": "Older Azure VM series (Dv2, Dv3) have a higher cost-to-performance ratio. Migrate to Dv5/Ev5 series for improved price-performance.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 15,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
    ],
    "short_living_instances": [
        {
            "id": "aws-co-10",
            "title": "Use Spot Instances for short-lived, fault-tolerant workloads",
            "description": "Instances that run for less than 2 hours repeatedly are ideal candidates for EC2 Spot Instances, saving up to 90% compared to on-demand pricing.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 70,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
        {
            "id": "gcp-co-10",
            "title": "Use Preemptible or Spot VMs for batch and ephemeral workloads",
            "description": "Short-lived compute tasks should leverage GCP Preemptible VMs (up to 60-91% discount) or Spot VMs for fault-tolerant batch processing.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 70,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/optimize-compute",
        },
    ],
    "abandoned_load_balancers": [
        {
            "id": "aws-co-11",
            "title": "Delete ALB/NLB with no registered or healthy targets",
            "description": "Load balancers with zero healthy targets or no traffic for 14+ days still incur hourly and LCU charges. Delete unused load balancers after confirming no dependency.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-11",
            "title": "Remove Azure Load Balancers with empty backend pools",
            "description": "Azure Load Balancers (Standard SKU) with no backend pool members incur charges without serving traffic. Delete after confirming no active dependencies.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 100,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-11",
            "title": "Delete GCP load balancers with no healthy backend services",
            "description": "GCP forwarding rules and backend services without healthy instances still incur forwarding rule charges. Remove unused load balancer configurations.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 100,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/monitor",
        },
    ],
    "abandoned_images": [
        {
            "id": "aws-co-12",
            "title": "Deregister unused AMIs and delete backing snapshots",
            "description": "AMIs not used to launch instances in 90+ days consume storage via their backing EBS snapshots. Deregister the AMI and delete associated snapshots.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-12",
            "title": "Delete unused Azure custom images from Compute Gallery",
            "description": "Custom VM images stored in Azure Compute Gallery (or as managed images) incur storage costs. Remove images that haven't been used to create VMs in 90+ days.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-12",
            "title": "Delete deprecated custom images in Compute Engine",
            "description": "GCP custom images consume storage. Delete images not used to launch an instance in over 90 days. Use deprecation flags to communicate before deletion.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/monitor",
        },
    ],
    "s3_intelligent_tiering": [
        {
            "id": "aws-co-13",
            "title": "Enable S3 Intelligent-Tiering for unpredictable access patterns",
            "description": "S3 buckets with mixed or declining access patterns benefit from Intelligent-Tiering, which automatically moves objects between frequent and infrequent access tiers. Saves 20-40% on storage.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 30,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
    ],
    "abandoned_kinesis_streams": [
        {
            "id": "aws-co-14",
            "title": "Delete Kinesis streams with no producer or consumer activity",
            "description": "Kinesis Data Streams charge per shard-hour regardless of usage. Streams with zero incoming PutRecord calls and inactive consumers for 30+ days should be deleted.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
    ],
    "inactive_users": [
        {
            "id": "aws-sec-01",
            "title": "Remove or disable IAM users with no API activity for 90 days",
            "description": "IAM users with no API calls (console or programmatic) for 90+ days represent a security risk. Disable credentials and review for deletion per least-privilege principle.",
            "framework": "AWS Well-Architected",
            "pillar": "Security",
            "severity": "high",
            "estimated_saving_pct": 0,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/identity-and-access-management.html",
        },
    ],
    "inactive_console_users": [
        {
            "id": "aws-sec-02",
            "title": "Disable console access for users inactive for 90+ days",
            "description": "IAM users who have not signed in to the AWS console for 90 days should have their console password disabled. Reduces the attack surface without deleting the user.",
            "framework": "AWS Well-Architected",
            "pillar": "Security",
            "severity": "medium",
            "estimated_saving_pct": 0,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/identity-and-access-management.html",
        },
    ],
    "instances_in_stopped_state": [
        {
            "id": "aws-co-15",
            "title": "Terminate or snapshot EC2 instances stopped for 7+ days",
            "description": "Stopped EC2 instances still incur EBS volume charges. If not needed, create an AMI and terminate. If needed later, restore from AMI to save on idle storage.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 80,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
        {
            "id": "azure-co-15",
            "title": "Review and deallocate Azure VMs in stopped (not deallocated) state",
            "description": "Azure VMs in 'Stopped' state (vs 'Stopped (deallocated)') continue to incur compute charges. Deallocate or delete VMs stopped for 7+ days.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 80,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-15",
            "title": "Delete or snapshot stopped Compute Engine instances after 7 days",
            "description": "Stopped GCP instances still incur persistent disk charges. Create a machine image and delete the instance if it's not expected to restart soon.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 80,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/monitor",
        },
    ],
    "obsolete_snapshot_chains": [
        {
            "id": "aws-co-16",
            "title": "Delete orphaned EBS snapshot chains",
            "description": "Incremental snapshot chains whose parent volume is deleted still consume storage. Delete the entire chain to reclaim space and reduce costs.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "low",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
    ],
    "rightsizing_rds": [
        {
            "id": "aws-co-17",
            "title": "Downsize RDS instances with <30% average CPU utilisation",
            "description": "RDS instances consistently under 30% CPU and with connection headroom can be downsized. Use Performance Insights and CloudWatch metrics to validate before resizing.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "high",
            "estimated_saving_pct": 40,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
    ],
    "instance_subscription": [
        {
            "id": "azure-co-17",
            "title": "Purchase Azure Reserved VM Instances for steady workloads",
            "description": "Use 1- or 3-year Azure Reserved VM Instances for workloads with predictable usage. Savings of up to 72% compared to pay-as-you-go.",
            "framework": "Azure Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "critical",
            "estimated_saving_pct": 45,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-compute",
        },
        {
            "id": "gcp-co-17",
            "title": "Commit to GCP Committed Use Discounts (CUDs) for baseline capacity",
            "description": "GCP CUDs provide up to 57% discount for 1-year or 70% for 3-year commitments on steady-state Compute Engine and Cloud SQL workloads.",
            "framework": "GCP Architecture Framework",
            "pillar": "Cost Optimization",
            "severity": "critical",
            "estimated_saving_pct": 45,
            "reference_url": "https://cloud.google.com/architecture/framework/cost-optimization/optimize-compute",
        },
    ],
    "cvos_opportunities": [
        {
            "id": "multi-co-01",
            "title": "Consolidate workloads to a single provider for volume discounts",
            "description": "Workloads spread across clouds may miss volume-based tiered pricing. Consolidating eligible workloads to one provider can unlock EDP (AWS), MACC (Azure), or CUD (GCP) discounts.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 20,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
    ],
    "nebius_migration": [
        {
            "id": "multi-co-02",
            "title": "Evaluate GPU workload migration to cost-effective providers",
            "description": "GPU-intensive ML/AI workloads (training, inference) may benefit from alternative providers with lower GPU-hour pricing. Benchmark performance parity before migrating.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 50,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
    ],
    "instance_migration": [
        {
            "id": "multi-co-03",
            "title": "Migrate instances to cheaper-equivalent cloud where pricing is lower",
            "description": "Regularly compare instance pricing across AWS, Azure, and GCP for equivalent vCPU/memory configurations. Migrate non-dependent workloads to the cheapest provider.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 25,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
    ],
    "insecure_security_groups": [
        {
            "id": "aws-sec-03",
            "title": "Restrict security groups allowing 0.0.0.0/0 on sensitive ports",
            "description": "Security groups with inbound rules allowing 0.0.0.0/0 on ports 22 (SSH), 3389 (RDP), 3306 (MySQL), or 5432 (PostgreSQL) violate least-privilege. Restrict to known CIDR ranges.",
            "framework": "AWS Well-Architected",
            "pillar": "Security",
            "severity": "critical",
            "estimated_saving_pct": 0,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/infrastructure-protection.html",
        },
        {
            "id": "azure-sec-03",
            "title": "Harden NSG rules permitting any-source on management ports",
            "description": "Azure NSGs with 'Any' source on ports 22/3389 expose resources to brute-force attacks. Use Just-In-Time VM access or restrict to bastion host IP ranges.",
            "framework": "Azure Well-Architected",
            "pillar": "Security",
            "severity": "critical",
            "estimated_saving_pct": 0,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/security/networking",
        },
        {
            "id": "gcp-sec-03",
            "title": "Remove overly permissive GCP firewall rules on management ports",
            "description": "GCP firewall rules allowing 0.0.0.0/0 ingress on SSH (22) or RDP (3389) should be restricted. Use IAP tunnels or OS Login for secure access.",
            "framework": "GCP Architecture Framework",
            "pillar": "Security",
            "severity": "critical",
            "estimated_saving_pct": 0,
            "reference_url": "https://cloud.google.com/architecture/framework/security/network-security",
        },
    ],
    "s3_public_buckets": [
        {
            "id": "aws-sec-04",
            "title": "Enable S3 Block Public Access on all buckets",
            "description": "S3 buckets with public ACLs or bucket policies risk data exposure. Enable Block Public Access at the account level and audit individual bucket policies.",
            "framework": "AWS Well-Architected",
            "pillar": "Security",
            "severity": "critical",
            "estimated_saving_pct": 0,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/data-protection.html",
        },
        {
            "id": "azure-sec-04",
            "title": "Disable anonymous access on Azure Blob Storage containers",
            "description": "Azure storage containers with 'Blob' or 'Container' public access level expose data publicly. Set access level to 'Private' and use SAS tokens for legitimate sharing.",
            "framework": "Azure Well-Architected",
            "pillar": "Security",
            "severity": "critical",
            "estimated_saving_pct": 0,
            "reference_url": "https://learn.microsoft.com/en-us/azure/well-architected/security/storage",
        },
    ],
    "idle_load_balancers": [
        {
            "id": "aws-co-25",
            "title": "Delete ALB/NLB with no registered or healthy targets",
            "description": "Load balancers with zero healthy targets or no traffic for 14+ days still incur hourly and LCU charges. Delete unused load balancers after confirming no dependency.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "medium",
            "estimated_saving_pct": 100,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/expenditure-and-usage-awareness.html",
        },
    ],
    "savings_plans": [
        {
            "id": "aws-co-26",
            "title": "Purchase Compute Savings Plans for consistent compute usage",
            "description": "Compute Savings Plans provide up to 66% discount compared to On-Demand pricing and apply automatically to EC2, Fargate, and Lambda usage across all regions.",
            "framework": "AWS Well-Architected",
            "pillar": "Cost Optimization",
            "severity": "critical",
            "estimated_saving_pct": 40,
            "reference_url": "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/select-the-best-pricing-model.html",
        },
    ],
}


def _generate_demo_items(rng: random.Random, rec_def: dict) -> list[dict]:
    """Generate realistic sample items for one recommendation type."""
    items: list[dict] = []
    count = rec_def["demo_count"]
    per_item_saving = round(rec_def["demo_saving"] / max(count, 1), 2)
    resource_prefixes = {
        "aws_cnr": ("i-", "vol-", "snap-", "arn:aws:"),
        "azure_cnr": ("/subscriptions/",),
        "gcp_cnr": ("projects/",),
    }

    for i in range(count):
        cloud = rng.choice(rec_def["cloud_types"])
        prefix = rng.choice(resource_prefixes.get(cloud, ("res-",)))
        items.append(
            {
                "id": f"{rec_def['type']}-item-{i + 1:03d}",
                "resource_id": f"{prefix}{rng.randint(100000, 999999):06x}",
                "resource_name": f"{rec_def['type'].replace('_', '-')}-resource-{i + 1}",
                "cloud_type": cloud,
                "region": rng.choice(["us-east-1", "eu-west-1", "us-west-2", "eastus", "us-central1"]),
                "saving": per_item_saving,
                "dismissed": False,
            }
        )
    return items


def _build_demo_overview() -> RecommendationsOverview:
    """Pre-compute the full recommendations overview with demo data."""
    rng = random.Random(hashlib.sha256(b"costpilot-recs").hexdigest())
    now_ts = int(time.time())

    recs: list[RecommendationType] = []
    total_saving = 0.0
    total_count = 0
    categories: dict[str, int] = {"cost": 0, "security": 0}

    for rec_def in _RECOMMENDATION_DEFS:
        items = _generate_demo_items(rng, rec_def)
        rule_dicts = _WELL_ARCHITECTED_RULES.get(rec_def["type"], [])
        rules = [WellArchitectedRule(**r) for r in rule_dicts]
        rec = RecommendationType(
            type=rec_def["type"],
            name=rec_def["name"],
            description=rec_def["description"],
            category=rec_def["category"],
            cloud_types=rec_def["cloud_types"],
            count=rec_def["demo_count"],
            saving=rec_def["demo_saving"],
            items=items,
            rules=rules,
        )
        recs.append(rec)
        total_saving += rec_def["demo_saving"]
        total_count += rec_def["demo_count"]
        categories[rec_def["category"]] += rec_def["demo_count"]

    return RecommendationsOverview(
        total_saving=round(total_saving, 2),
        total_count=total_count,
        last_run=now_ts - 3600,  # 1 hour ago
        next_run=now_ts + 3600 * 23,  # ~23 hours from now
        categories=categories,
        recommendations=recs,
    )


_DEMO_OVERVIEW = _build_demo_overview()


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def get_recommendations_overview(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
    cloud_account_ids: Optional[list[str]] = None,
    db: Optional[AsyncSession] = None,
) -> RecommendationsOverview:
    """Return the full recommendations overview, optionally filtered by cloud accounts.
    
    If cloud accounts are connected, returns real recommendations from CSP APIs.
    If no cloud accounts exist, returns demo data for preview purposes.
    """
    import time
    from sqlalchemy import select, func
    from app.cloud_accounts.models import CloudAccount
    
    all_recs: list[RecommendationType] = []
    total_saving = 0.0
    total_count = 0
    categories: dict[str, int] = {}
    now_ts = int(time.time())
    has_cloud_accounts = False
    
    # Check if organization has any cloud accounts
    if db is not None:
        try:
            count_result = await db.execute(
                select(func.count(CloudAccount.id)).where(
                    CloudAccount.organization_id == org_id,
                    CloudAccount.deleted_at.is_(None),
                )
            )
            account_count = count_result.scalar() or 0
            has_cloud_accounts = account_count > 0
        except Exception:
            pass
    
    # If no cloud accounts, return empty data (no recommendations)
    if not has_cloud_accounts:
        return RecommendationsOverview(
            total_saving=0.0,
            total_count=0,
            last_run=None,
            next_run=None,
            categories={},
            recommendations=[],
        )
    
    # Fetch CSP native recommendations (real data from AWS/Azure/GCP)
    if db is not None:
        from app.recommendations.csp_service import fetch_csp_recommendations
        
        try:
            csp_recs = await fetch_csp_recommendations(db, mongo_db, org_id, cloud_account_ids)
            for rec in csp_recs:
                all_recs.append(rec)
                total_saving += rec.saving
                total_count += rec.count
                categories[rec.category] = categories.get(rec.category, 0) + rec.count
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to fetch CSP recommendations: %s", e)
    
    # Merge custom rule recommendations
    if db is not None:
        from app.recommendation_rules.service import evaluate_custom_rules
        
        try:
            custom_recs = await evaluate_custom_rules(db, org_id)
            for rec in custom_recs:
                all_recs.append(rec)
                total_saving += rec.saving
                total_count += rec.count
                categories[rec.category] = categories.get(rec.category, 0) + rec.count
        except Exception:
            pass  # Custom rules fetch failures are non-fatal
    
    return RecommendationsOverview(
        total_saving=round(total_saving, 2),
        total_count=total_count,
        last_run=now_ts - 300,  # 5 minutes ago (simulated last run)
        next_run=now_ts + 3600,  # 1 hour from now
        categories=categories,
        recommendations=all_recs,
    )


async def get_recommendation_by_type(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
    rec_type: str,
    db: Optional[AsyncSession] = None,
) -> RecommendationType | None:
    """Return a single recommendation type with its items."""
    from sqlalchemy import select, func
    from app.cloud_accounts.models import CloudAccount
    
    has_cloud_accounts = False
    
    # Check if organization has any cloud accounts
    if db is not None:
        try:
            count_result = await db.execute(
                select(func.count(CloudAccount.id)).where(
                    CloudAccount.organization_id == org_id,
                    CloudAccount.deleted_at.is_(None),
                )
            )
            account_count = count_result.scalar() or 0
            has_cloud_accounts = account_count > 0
        except Exception:
            pass
    
    # If no cloud accounts, return None (no recommendations available)
    if not has_cloud_accounts:
        return None
    
    # Check CSP native recommendations first (for csp_ prefixed types)
    if db is not None:
        from app.recommendations.csp_service import fetch_csp_recommendations
        
        try:
            csp_recs = await fetch_csp_recommendations(db, mongo_db, org_id)
            for rec in csp_recs:
                if rec.type == rec_type:
                    return rec
        except Exception:
            pass
    
    # Check custom rules
    if db is not None and rec_type.startswith("custom_rule_"):
        from app.recommendation_rules.service import evaluate_custom_rules
        
        custom_recs = await evaluate_custom_rules(db, org_id)
        for rec in custom_recs:
            if rec.type == rec_type:
                return rec
    
    return None


async def dismiss_recommendation(
    mongo_db: AsyncIOMotorDatabase,
    org_id: str,
    rec_id: str,
) -> dict:
    """Toggle the dismissed flag on a recommendation item in MongoDB.

    Updates the dismissed status for a recommendation item stored in the
    recommendations collection.
    """
    RECOMMENDATIONS_COLLECTION = "recommendations"
    
    try:
        collection = mongo_db[RECOMMENDATIONS_COLLECTION]

        # Dismiss state is organization-scoped.
        item = await collection.find_one({"id": rec_id, "organization_id": org_id})
        current_dismissed = item.get("dismissed", False) if item else False
        new_dismissed = not current_dismissed

        now_ts = int(time.time())
        await collection.update_one(
            {"id": rec_id, "organization_id": org_id},
            {
                "$set": {
                    "id": rec_id,
                    "organization_id": org_id,
                    "dismissed": new_dismissed,
                    "updated_at": now_ts,
                },
                "$setOnInsert": {
                    "created_at": now_ts,
                },
            },
            upsert=True,
        )

        return {"id": rec_id, "dismissed": new_dismissed}
    except Exception as e:
        return {"id": rec_id, "error": str(e)}
