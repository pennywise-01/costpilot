"""Base class for advisor-finding ingestors."""

from abc import ABC, abstractmethod

from app.advisor_findings.schemas import NormalizedAdvisorFinding


class AdvisorIngestor(ABC):
    """Abstract base for per-provider advisor ingestors.

    Implementations:
        - `aws_compute_optimizer.AwsComputeOptimizerIngestor`
        - `aws_trusted_advisor.AwsTrustedAdvisorIngestor`
        - `aws_cost_optimization_hub.AwsCostOptimizationHubIngestor`
        - `azure_advisor.AzureAdvisorIngestor`
        - `gcp_recommender.GcpRecommenderIngestor`
    """

    #: Stable identifier persisted in `advisor_findings.source_service`.
    source_service: str = ""

    @abstractmethod
    async def fetch(self, config: dict) -> list[NormalizedAdvisorFinding]:
        """Pull findings from the provider's advisor API.

        Args:
            config: Decrypted cloud-account config dict (credentials etc.)
        """
        ...
