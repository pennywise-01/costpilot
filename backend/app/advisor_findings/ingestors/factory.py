"""Factory: pick the right ingestor for a cloud account type."""

from app.advisor_findings.ingestors.aws_compute_optimizer import AwsComputeOptimizerIngestor
from app.advisor_findings.ingestors.aws_cost_optimization_hub import AwsCostOptimizationHubIngestor
from app.advisor_findings.ingestors.aws_trusted_advisor import AwsTrustedAdvisorIngestor
from app.advisor_findings.ingestors.azure_advisor import AzureAdvisorIngestor
from app.advisor_findings.ingestors.base import AdvisorIngestor
from app.advisor_findings.ingestors.gcp_recommender import GcpRecommenderIngestor
from app.shared.enums import CloudType


def get_ingestors_for(cloud_type: CloudType) -> list[AdvisorIngestor]:
    """Return the chain of ingestors that should run for this cloud account.

    A single account can have multiple advisor APIs (e.g. AWS exposes
    Compute Optimizer + Trusted Advisor + Cost Optimization Hub). We
    return them as a list so the service can iterate.
    """
    if cloud_type == CloudType.AWS:
        return [
            AwsComputeOptimizerIngestor(),
            AwsTrustedAdvisorIngestor(),
            AwsCostOptimizationHubIngestor(),
        ]
    if cloud_type in (CloudType.AZURE, CloudType.AZURE_TENANT):
        return [AzureAdvisorIngestor()]
    if cloud_type in (CloudType.GCP, CloudType.GCP_TENANT):
        return [GcpRecommenderIngestor()]
    return []
