"""Dashboard CRUD + layout save endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.enterprise.modules.rbac.dependencies import require_org_permission
from app.organizations.models import Employee
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member

from app.dashboards.schemas import (
    BatchWidgetDataRequest,
    BatchWidgetDataResponse,
    DashboardCreate,
    DashboardDetail,
    DashboardDuplicate,
    DashboardListItem,
    DashboardUpdate,
)
from app.dashboards import service as svc

router = APIRouter()


# --- READ permission dependency ---
_read_perm = Depends(require_org_permission(PermissionAction.READ, RBACResourceType.EXPENSE))
_manage_perm = Depends(require_org_permission(PermissionAction.MANAGE, RBACResourceType.EXPENSE))


@router.get(
    "/organizations/{org_id}/dashboards",
    response_model=list[DashboardListItem],
    dependencies=[_read_perm],
)
async def list_dashboards(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    dashboards = await svc.list_dashboards(db, org_id)
    return [DashboardListItem.model_validate(d) for d in dashboards]


@router.post(
    "/organizations/{org_id}/dashboards",
    response_model=DashboardDetail,
    dependencies=[_manage_perm],
)
async def create_dashboard(
    org_id: str,
    data: DashboardCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await svc.create_dashboard(
        db, org_id, member.auth_user_id, data.name, data.template_dashboard_id
    )
    await db.commit()
    await db.refresh(dashboard)
    return DashboardDetail.model_validate(dashboard)


@router.get(
    "/organizations/{org_id}/dashboards/{dashboard_id}",
    response_model=DashboardDetail,
    dependencies=[_read_perm],
)
async def get_dashboard(
    org_id: str,
    dashboard_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await svc.get_dashboard(db, dashboard_id, org_id)
    return DashboardDetail.model_validate(dashboard)


@router.put(
    "/organizations/{org_id}/dashboards/{dashboard_id}",
    response_model=DashboardDetail,
    dependencies=[_manage_perm],
)
async def update_dashboard(
    org_id: str,
    dashboard_id: str,
    data: DashboardUpdate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await svc.update_dashboard(
        db,
        dashboard_id,
        org_id,
        member.auth_user_id,
        name=data.name,
        layout_config=[item.model_dump() for item in data.layout_config] if data.layout_config else None,
        widget_config={k: v.model_dump() for k, v in data.widget_config.items()} if data.widget_config else None,
        version=data.version,
    )
    await db.commit()
    await db.refresh(dashboard)
    return DashboardDetail.model_validate(dashboard)


@router.delete(
    "/organizations/{org_id}/dashboards/{dashboard_id}",
    dependencies=[_manage_perm],
)
async def delete_dashboard(
    org_id: str,
    dashboard_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    await svc.delete_dashboard(db, dashboard_id, org_id)
    await db.commit()
    return {"detail": "Dashboard deleted"}


@router.put(
    "/organizations/{org_id}/dashboards/{dashboard_id}/set-default",
    response_model=DashboardDetail,
    dependencies=[_manage_perm],
)
async def set_default_dashboard(
    org_id: str,
    dashboard_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await svc.set_default_dashboard(db, dashboard_id, org_id, member.auth_user_id)
    await db.commit()
    await db.refresh(dashboard)
    return DashboardDetail.model_validate(dashboard)


@router.post(
    "/organizations/{org_id}/dashboards/{dashboard_id}/revert",
    response_model=DashboardDetail,
    dependencies=[_manage_perm],
)
async def revert_dashboard(
    org_id: str,
    dashboard_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await svc.revert_dashboard(db, dashboard_id, org_id, member.auth_user_id)
    await db.commit()
    await db.refresh(dashboard)
    return DashboardDetail.model_validate(dashboard)


@router.post(
    "/organizations/{org_id}/dashboards/{dashboard_id}/duplicate",
    response_model=DashboardDetail,
    dependencies=[_manage_perm],
)
async def duplicate_dashboard(
    org_id: str,
    dashboard_id: str,
    data: DashboardDuplicate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await svc.duplicate_dashboard(
        db, dashboard_id, org_id, member.auth_user_id, data.name
    )
    await db.commit()
    await db.refresh(dashboard)
    return DashboardDetail.model_validate(dashboard)


# --- Batch widget data endpoint (Phase 2) ---
@router.post(
    "/organizations/{org_id}/dashboards/widgets/data",
    response_model=BatchWidgetDataResponse,
    dependencies=[_read_perm],
)
async def batch_widget_data(
    org_id: str,
    data: BatchWidgetDataRequest,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboards.batch import fetch_batch_widget_data
    return await fetch_batch_widget_data(db, org_id, data.widgets)
