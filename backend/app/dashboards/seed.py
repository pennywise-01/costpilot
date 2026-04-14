"""Default dashboard seeder — called synchronously inside org creation."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboards.models import Dashboard

logger = logging.getLogger(__name__)

DEFAULT_LAYOUT = [
    {"i": "stat-monthly",   "x": 0, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
    {"i": "stat-forecast",  "x": 3, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
    {"i": "stat-lastmonth", "x": 6, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
    {"i": "stat-savings",   "x": 9, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
    {"i": "chart-trend",    "x": 0, "y": 2,  "w": 12, "h": 6, "minW": 6, "minH": 4},
    {"i": "table-resources","x": 0, "y": 8,  "w": 7, "h": 6, "minW": 4, "minH": 4},
    {"i": "list-recs",      "x": 7, "y": 8,  "w": 5, "h": 6, "minW": 4, "minH": 4},
    {"i": "list-pools",     "x": 0, "y": 14, "w": 6, "h": 5, "minW": 4, "minH": 3},
    {"i": "list-accounts",  "x": 6, "y": 14, "w": 6, "h": 5, "minW": 4, "minH": 3},
]

DEFAULT_WIDGET_CONFIG = {
    "stat-monthly":   {"type": "stat_card", "metric": "monthly_spend",  "title": "Monthly Spend",   "color": "#1677ff", "icon": "DollarOutlined"},
    "stat-forecast":  {"type": "stat_card", "metric": "forecast",       "title": "Forecast",        "color": "#722ed1", "icon": "FundOutlined"},
    "stat-lastmonth": {"type": "stat_card", "metric": "last_month_spend","title": "Last Month",     "color": "#52c41a", "icon": "CalendarOutlined"},
    "stat-savings":   {"type": "stat_card", "metric": "potential_savings","title": "Potential Savings","color": "#fa8c16","icon": "ThunderboltOutlined"},
    "chart-trend":    {"type": "area_chart", "metric": "cost_trend",    "title": "Cost Trend",      "dateRange": 30, "smooth": True},
    "table-resources":{"type": "table",      "metric": "top_resources", "title": "Top Expensive Resources"},
    "list-recs":      {"type": "progress_list","metric": "recommendation_categories","title": "Recommendations Summary"},
    "list-pools":     {"type": "progress_list","metric": "pool_status", "title": "Pools Requiring Attention"},
    "list-accounts":  {"type": "status_list", "metric": "cloud_account_health","title": "Cloud Accounts"},
}


def _slugify(name: str) -> str:
    """Convert a dashboard name to a URL-friendly slug."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "dashboard"
    return slug


async def seed_default_dashboard(
    db: AsyncSession,
    org_id: str,
    user_id: str,
) -> Dashboard:
    """Create the default dashboard for a new organization.

    Must be called inside the org creation transaction so that GET /dashboards
    always returns at least one result on first load.
    """
    slug = "default"

    dashboard = Dashboard(
        organization_id=org_id,
        name="Default Dashboard",
        slug=slug,
        is_default=True,
        layout_config=DEFAULT_LAYOUT,
        previous_layout_config=None,
        widget_config=DEFAULT_WIDGET_CONFIG,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(dashboard)
    await db.flush()

    logger.info("Seeded default dashboard for org %s", org_id)
    return dashboard
