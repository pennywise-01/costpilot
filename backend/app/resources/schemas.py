from pydantic import BaseModel

class PartialFailure(BaseModel):
    account_id: str
    account_name: str
    cloud_type: str
    error: str


class ResourceResponse(BaseModel):
    id: str
    name: str
    cloud_resource_id: str
    resource_type: str | None = None
    cloud_account_id: str | None = None
    cloud_account_name: str | None = None
    cloud_type: str | None = None
    region: str | None = None
    pool_id: str | None = None
    pool_name: str | None = None
    owner_id: str | None = None
    owner_name: str | None = None
    tags: dict = {}
    first_seen: int | None = None
    last_seen: int | None = None
    total_cost: float = 0
    daily_cost: float = 0
    active: bool = True

class ResourceListResponse(BaseModel):
    resources: list[ResourceResponse] = []
    total_count: int = 0
    limit: int = 50
    offset: int = 0
    partial_failures: list[PartialFailure] = []
    has_errors: bool = False

class ResourceDetail(ResourceResponse):
    meta: dict = {}
    recommendations: list[dict] = []
    daily_expenses: list[dict] = []
