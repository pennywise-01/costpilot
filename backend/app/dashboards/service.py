"""Dashboard business logic — CRUD, set-default, revert, duplicate."""

import json
import logging
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dashboards.models import Dashboard
from app.dashboards.seed import _slugify
from app.dashboards.schemas import VALID_METRICS_BY_TYPE
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.shared.utils.time import utc_now

logger = logging.getLogger(__name__)

# --- Helpers ---

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _validate_layout_config(layout_config: list[dict]) -> None:
    """Validate layout config items have required fields and are within bounds."""
    required_fields = {"i", "x", "y", "w", "h"}
    for item in layout_config:
        missing = required_fields - set(item.keys())
        if missing:
            raise BadRequestError(f"Layout item missing fields: {missing}")
        if not (0 <= item["x"] < 12):
            raise BadRequestError(f"Layout item x out of bounds: {item['x']}")
        if not (0 <= item["y"] < 1000):
            raise BadRequestError(f"Layout item y out of bounds: {item['y']}")
        if not (1 <= item["w"] <= 12):
            raise BadRequestError(f"Layout item w out of bounds: {item['w']}")
        if not (1 <= item["h"] <= 20):
            raise BadRequestError(f"Layout item h out of bounds: {item['h']}")

    # Size check
    size_kb = len(json.dumps(layout_config).encode()) / 1024
    if size_kb > settings.DASHBOARD_LAYOUT_MAX_SIZE_KB:
        raise BadRequestError(
            f"Layout config too large ({size_kb:.1f}KB > {settings.DASHBOARD_LAYOUT_MAX_SIZE_KB}KB)"
        )


def _validate_widget_config(widget_config: dict) -> None:
    """Validate widget config entries against whitelist."""
    for widget_id, cfg in widget_config.items():
        wtype = cfg.get("type", "")
        metric = cfg.get("metric", "")
        if wtype not in VALID_METRICS_BY_TYPE:
            raise BadRequestError(f"Unknown widget type: {wtype}")
        valid_metrics = VALID_METRICS_BY_TYPE[wtype]
        if metric not in valid_metrics:
            raise BadRequestError(f"Invalid metric '{metric}' for widget type '{wtype}'")

    if len(widget_config) > settings.DASHBOARD_MAX_WIDGETS:
        raise BadRequestError(
            f"Too many widgets ({len(widget_config)} > {settings.DASHBOARD_MAX_WIDGETS})"
        )

    size_kb = len(json.dumps(widget_config).encode()) / 1024
    if size_kb > settings.DASHBOARD_WIDGET_CONFIG_MAX_SIZE_KB:
        raise BadRequestError(
            f"Widget config too large ({size_kb:.1f}KB > {settings.DASHBOARD_WIDGET_CONFIG_MAX_SIZE_KB}KB)"
        )


async def _get_dashboard_or_404(db: AsyncSession, dashboard_id: str, org_id: str) -> Dashboard:
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.id == dashboard_id,
            Dashboard.organization_id == org_id,
            Dashboard.deleted_at.is_(None),
        ).limit(1)
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise NotFoundError("Dashboard not found")
    return dashboard


# --- CRUD ---


async def list_dashboards(db: AsyncSession, org_id: str) -> list[Dashboard]:
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.organization_id == org_id,
            Dashboard.deleted_at.is_(None),
        ).order_by(Dashboard.is_default.desc(), Dashboard.name.asc())
    )
    return list(result.scalars().all())


async def get_dashboard(db: AsyncSession, dashboard_id: str, org_id: str) -> Dashboard:
    return await _get_dashboard_or_404(db, dashboard_id, org_id)


async def create_dashboard(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    name: str,
    template_dashboard_id: str | None = None,
) -> Dashboard:
    # Check max dashboards per org
    count_result = await db.execute(
        select(func.count(Dashboard.id)).where(
            Dashboard.organization_id == org_id,
            Dashboard.deleted_at.is_(None),
        )
    )
    count = count_result.scalar() or 0
    if count >= settings.DASHBOARD_MAX_PER_ORG:
        raise BadRequestError(
            f"Maximum dashboards reached ({settings.DASHBOARD_MAX_PER_ORG} per org)"
        )

    slug = _slugify(name)

    # Ensure slug uniqueness within org
    existing = await db.execute(
        select(Dashboard).where(
            Dashboard.organization_id == org_id,
            Dashboard.slug == slug,
            Dashboard.deleted_at.is_(None),
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        # Append suffix on collision
        for suffix in range(2, 100):
            candidate = f"{slug}-{suffix}"
            existing = await db.execute(
                select(Dashboard).where(
                    Dashboard.organization_id == org_id,
                    Dashboard.slug == candidate,
                    Dashboard.deleted_at.is_(None),
                ).limit(1)
            )
            if not existing.scalar_one_or_none():
                slug = candidate
                break
        else:
            raise ConflictError("Could not generate unique slug")

    # If template specified, copy layout and widget config
    layout_config = []
    widget_config = {}
    if template_dashboard_id:
        template = await _get_dashboard_or_404(db, template_dashboard_id, org_id)
        layout_config = template.layout_config
        widget_config = template.widget_config

    dashboard = Dashboard(
        organization_id=org_id,
        name=name,
        slug=slug,
        is_default=False,
        layout_config=layout_config,
        previous_layout_config=None,
        widget_config=widget_config,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(dashboard)
    await db.flush()

    logger.info("Created dashboard '%s' (slug=%s) for org %s", name, slug, org_id)
    return dashboard


async def update_dashboard(
    db: AsyncSession,
    dashboard_id: str,
    org_id: str,
    user_id: str,
    name: str | None = None,
    layout_config: list[dict] | None = None,
    widget_config: dict | None = None,
    version: int = 1,
) -> Dashboard:
    dashboard = await _get_dashboard_or_404(db, dashboard_id, org_id)

    # Optimistic locking check
    if dashboard.version_id != version:
        raise ConflictError(
            "Dashboard was modified by another user. Refresh to see the latest."
        )

    # On save: copy current layout_config → previous_layout_config before applying new values
    if layout_config is not None or widget_config is not None:
        _validate_layout_config(layout_config if layout_config is not None else dashboard.layout_config)
        if widget_config is not None:
            _validate_widget_config(widget_config)

        # Snapshot current layout for revert
        dashboard.previous_layout_config = dashboard.layout_config

    if name is not None:
        dashboard.name = name
        # Slug is immutable — never updated on rename

    if layout_config is not None:
        dashboard.layout_config = layout_config

    if widget_config is not None:
        dashboard.widget_config = widget_config

    dashboard.updated_by = user_id
    # Increment version for optimistic locking
    dashboard.version_id += 1
    await db.flush()

    logger.info("Updated dashboard %s (version %d→%d)", dashboard_id, version, dashboard.version_id)
    return dashboard


async def delete_dashboard(db: AsyncSession, dashboard_id: str, org_id: str) -> None:
    dashboard = await _get_dashboard_or_404(db, dashboard_id, org_id)

    # Cannot delete the last dashboard
    count_result = await db.execute(
        select(func.count(Dashboard.id)).where(
            Dashboard.organization_id == org_id,
            Dashboard.deleted_at.is_(None),
        )
    )
    count = count_result.scalar() or 0
    if count <= 1:
        raise BadRequestError("Cannot delete the last dashboard in the organization")

    # Cannot delete the default dashboard — must set another as default first
    if dashboard.is_default:
        raise BadRequestError(
            "Cannot delete the default dashboard. Set another dashboard as default first."
        )

    dashboard.deleted_at = utc_now()
    await db.flush()

    logger.info("Soft-deleted dashboard %s from org %s", dashboard_id, org_id)


async def set_default_dashboard(
    db: AsyncSession,
    dashboard_id: str,
    org_id: str,
    user_id: str,
) -> Dashboard:
    dashboard = await _get_dashboard_or_404(db, dashboard_id, org_id)

    if dashboard.is_default:
        return dashboard  # Already default

    # Unset current default(s) — the partial unique index enforces at most one,
    # but we do it explicitly for clarity
    result = await db.execute(
        select(Dashboard).where(
            Dashboard.organization_id == org_id,
            Dashboard.is_default == True,
            Dashboard.deleted_at.is_(None),
        )
    )
    for current_default in result.scalars().all():
        current_default.is_default = False

    dashboard.is_default = True
    dashboard.updated_by = user_id
    dashboard.version_id += 1
    await db.flush()

    logger.info("Set dashboard %s as default for org %s", dashboard_id, org_id)
    return dashboard


async def revert_dashboard(
    db: AsyncSession,
    dashboard_id: str,
    org_id: str,
    user_id: str,
) -> Dashboard:
    dashboard = await _get_dashboard_or_404(db, dashboard_id, org_id)

    if dashboard.previous_layout_config is None:
        raise ConflictError("Nothing to revert — no previous layout saved")

    # Swap: current → previous, previous → current
    current = dashboard.layout_config
    dashboard.layout_config = dashboard.previous_layout_config
    dashboard.previous_layout_config = current
    dashboard.updated_by = user_id
    dashboard.version_id += 1
    await db.flush()

    logger.info("Reverted dashboard %s to previous layout", dashboard_id)
    return dashboard


async def duplicate_dashboard(
    db: AsyncSession,
    dashboard_id: str,
    org_id: str,
    user_id: str,
    new_name: str,
) -> Dashboard:
    source = await _get_dashboard_or_404(db, dashboard_id, org_id)
    return await create_dashboard(
        db,
        org_id,
        user_id,
        name=new_name,
        template_dashboard_id=source.id,
    )
