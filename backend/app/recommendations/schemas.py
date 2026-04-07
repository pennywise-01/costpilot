from pydantic import BaseModel


class WellArchitectedRule(BaseModel):
    id: str
    title: str
    description: str
    framework: str  # "AWS Well-Architected" | "Azure Well-Architected" | "GCP Architecture"
    pillar: str  # e.g. "Cost Optimization", "Security", "Reliability"
    severity: str  # "critical" | "high" | "medium" | "low"
    estimated_saving_pct: float = 0  # 0-100, estimated % saving per affected resource
    reference_url: str = ""


class RecommendationType(BaseModel):
    type: str
    name: str
    description: str
    category: str  # "cost" or "security"
    cloud_types: list[str] = []
    count: int = 0
    saving: float = 0
    items: list[dict] = []
    rules: list[WellArchitectedRule] = []
    source: str = "builtin"  # "builtin" | "custom_rule" | "csp_native"
    source_cloud_account_id: str = ""


class RecommendationsOverview(BaseModel):
    total_saving: float = 0
    total_count: int = 0
    last_run: int | None = None
    next_run: int | None = None
    categories: dict[str, int] = {}
    recommendations: list[RecommendationType] = []
