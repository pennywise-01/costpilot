from app.recommendations.adapters.base import RecommenderAdapter
from app.recommendations.adapters.aws import AwsRecommenderAdapter
from app.recommendations.adapters.azure import AzureRecommenderAdapter
from app.recommendations.adapters.gcp import GcpRecommenderAdapter
from app.shared.enums import CloudType


def get_recommender_adapter(cloud_type: CloudType) -> RecommenderAdapter | None:
    """Factory: return the appropriate recommender adapter for the given cloud type."""
    adapters = {
        CloudType.AWS: AwsRecommenderAdapter,
        CloudType.AZURE: AzureRecommenderAdapter,
        CloudType.GCP: GcpRecommenderAdapter,
    }
    adapter_cls = adapters.get(cloud_type)
    return adapter_cls() if adapter_cls else None
