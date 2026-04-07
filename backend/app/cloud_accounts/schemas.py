from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.enums import CloudType
from app.shared.pagination import PaginatedResponse


class CloudAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    type: CloudType
    config: dict


class CloudAccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    config: dict | None = None
    auto_import: bool | None = None
    process_recommendations: bool | None = None


class CloudAccountResponse(BaseModel):
    id: str
    name: str
    type: CloudType
    organization_id: str
    auto_import: bool
    last_import_at: int | None
    account_id: str
    process_recommendations: bool
    created_at: datetime
    permission_warnings: list[str] = Field(
        default_factory=list,
        description="List of permissions that are missing or insufficient for least-privilege access",
    )

    model_config = {"from_attributes": True}


class CloudAccountListItem(CloudAccountResponse):
    """Lightweight cloud account info for list views (no live data)."""
    pass


class CloudAccountDetail(CloudAccountResponse):
    """Full cloud account details with live data from cloud provider."""
    monthly_cost: float = 0
    forecast: float = 0
    last_month_cost: float = 0
    resources_count: int = 0
    # Indicates if this data was fetched from cloud API or is from cache/empty
    data_source: str = "live"  # "live", "cache", or "unavailable"
    cached_at: datetime | None = None


class PaginatedCloudAccounts(PaginatedResponse[CloudAccountListItem]):
    """Paginated response for cloud accounts list."""
    pass
