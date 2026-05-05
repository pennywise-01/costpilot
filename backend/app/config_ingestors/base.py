"""Base class for config-snapshot ingestors (Tier-2 asset inventory)."""

from abc import ABC, abstractmethod

from app.config_ingestors.schemas import NormalizedResourceConfig


class ConfigIngestor(ABC):
    """Abstract base for per-provider config ingestors.

    Implementations:
        - `aws_config.AwsConfigIngestor`
        - `azure_resource_graph.AzureResourceGraphIngestor`
        - `gcp_cloud_asset.GcpCloudAssetIngestor`
    """

    source_service: str = ""

    @abstractmethod
    async def fetch(self, config: dict) -> list[NormalizedResourceConfig]:
        """Pull a resource-config snapshot from the provider.

        Args:
            config: Decrypted cloud-account config dict (credentials etc.)
        """
        ...
