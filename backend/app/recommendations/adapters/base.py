from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NormalizedRecommendation:
    """A single recommendation item normalized from any CSP."""
    rec_type: str  # e.g. "rightsizing", "idle_resource"
    name: str
    description: str
    category: str  # "cost" or "security"
    resource_id: str = ""
    resource_name: str = ""
    cloud_type: str = ""
    region: str = ""
    source_service: str = ""  # e.g. "AWS Cost Explorer", "Azure Advisor"
    saving: float = 0.0
    metadata: dict = field(default_factory=dict)


class RecommenderAdapter(ABC):
    """Abstract base class for CSP recommendation adapters."""

    @abstractmethod
    async def fetch_recommendations(self, config: dict) -> list[NormalizedRecommendation]:
        """Fetch recommendations from the CSP and return normalized results.

        Args:
            config: Cloud account configuration dict containing credentials/settings.

        Returns:
            List of normalized recommendation items.
        """
        ...
