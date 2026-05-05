"""Factory: pick the right config ingestor for a cloud account type."""

from app.config_ingestors.aws_config import AwsConfigIngestor
from app.config_ingestors.azure_resource_graph import AzureResourceGraphIngestor
from app.config_ingestors.base import ConfigIngestor
from app.config_ingestors.gcp_cloud_asset import GcpCloudAssetIngestor
from app.shared.enums import CloudType


def get_config_ingestors_for(cloud_type: CloudType) -> list[ConfigIngestor]:
    """Return the config ingestors for a cloud account type."""
    if cloud_type == CloudType.AWS:
        return [AwsConfigIngestor()]
    if cloud_type in (CloudType.AZURE, CloudType.AZURE_TENANT):
        return [AzureResourceGraphIngestor()]
    if cloud_type in (CloudType.GCP, CloudType.GCP_TENANT):
        return [GcpCloudAssetIngestor()]
    return []
