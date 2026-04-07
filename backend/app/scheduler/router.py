"""Scheduler router - API endpoints for scheduler management."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.enterprise.modules.rbac.dependencies import require_org_permission
from app.shared.org_access import get_current_org_member
from app.database import get_db
from app.organizations.models import Employee
from app.scheduler.schemas import (
    DeadLetterJobListResponse,
    DeadLetterJobResponse,
    ManualTriggerRequest,
    ManualTriggerResponse,
    OrganizationSchedulerStats,
    RetryDeadLetterJobResponse,
    SchedulerConfigCreate,
    SchedulerConfigListResponse,
    SchedulerConfigResponse,
    SchedulerConfigUpdate,
    SchedulerLogListResponse,
    SchedulerLogResponse,
    SchedulerRunListResponse,
    SchedulerRunResponse,
    SchedulerStats,
    SchedulerStatsResponse,
    ToggleSchedulerRequest,
    ToggleSchedulerResponse,
)
from app.scheduler.service import (
    abandon_dead_letter_job,
    create_scheduler_config,
    delete_scheduler_config,
    get_dead_letter_job,
    get_organization_scheduler_stats,
    get_scheduler_config,
    get_scheduler_run,
    get_scheduler_stats,
    list_dead_letter_jobs,
    list_scheduler_configs,
    list_scheduler_logs,
    list_scheduler_runs,
    retry_dead_letter_job,
    toggle_scheduler,
    trigger_scheduler_manual,
    update_scheduler_config,
)
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.exceptions import BadRequestError, NotFoundError

router = APIRouter(tags=["Scheduler"])


@router.post(
    "/organizations/{org_id}/schedulers",
    response_model=SchedulerConfigResponse,
    status_code=201,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.ENTERPRISE))],
)
async def create_scheduler(
    org_id: str,
    data: SchedulerConfigCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new scheduler configuration."""
    try:
        config = await create_scheduler_config(
            db, org_id, str(current_user.id), data
        )
        return SchedulerConfigResponse.model_validate(config)
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/organizations/{org_id}/schedulers",
    response_model=SchedulerConfigListResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def list_schedulers(
    org_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List all scheduler configurations for an organization."""
    configs, total = await list_scheduler_configs(db, org_id, skip, limit)
    return SchedulerConfigListResponse(
        items=[SchedulerConfigResponse.model_validate(c) for c in configs],
        total=total,
    )


@router.get(
    "/organizations/{org_id}/schedulers/{scheduler_id}",
    response_model=SchedulerConfigResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def get_scheduler(
    org_id: str,
    scheduler_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific scheduler configuration."""
    try:
        config = await get_scheduler_config(db, org_id, scheduler_id)
        return SchedulerConfigResponse.model_validate(config)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch(
    "/organizations/{org_id}/schedulers/{scheduler_id}",
    response_model=SchedulerConfigResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.UPDATE, RBACResourceType.ENTERPRISE))],
)
async def update_scheduler(
    org_id: str,
    scheduler_id: str,
    data: SchedulerConfigUpdate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduler configuration."""
    try:
        config = await update_scheduler_config(db, org_id, scheduler_id, data)
        return SchedulerConfigResponse.model_validate(config)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/organizations/{org_id}/schedulers/{scheduler_id}",
    status_code=204,
    dependencies=[Depends(require_org_permission(PermissionAction.DELETE, RBACResourceType.ENTERPRISE))],
)
async def delete_scheduler(
    org_id: str,
    scheduler_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduler configuration."""
    try:
        await delete_scheduler_config(db, org_id, scheduler_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/organizations/{org_id}/schedulers/{scheduler_id}/toggle",
    response_model=ToggleSchedulerResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.MANAGE, RBACResourceType.ENTERPRISE))],
)
async def toggle_scheduler_endpoint(
    org_id: str,
    scheduler_id: str,
    data: ToggleSchedulerRequest,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a scheduler."""
    try:
        result = await toggle_scheduler(db, org_id, scheduler_id, data.is_enabled)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/organizations/{org_id}/schedulers/{scheduler_id}/trigger",
    response_model=ManualTriggerResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.MANAGE, RBACResourceType.ENTERPRISE))],
)
async def trigger_scheduler(
    org_id: str,
    scheduler_id: str,
    data: ManualTriggerRequest | None = None,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a scheduler run."""
    try:
        data = data or ManualTriggerRequest()
        result = await trigger_scheduler_manual(
            db,
            org_id,
            scheduler_id,
            str(current_user.id),
            override_expenses=data.collect_expenses,
            override_resources=data.collect_resources,
            override_recommendations=data.collect_recommendations,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/organizations/{org_id}/schedulers/{scheduler_id}/stats",
    response_model=SchedulerStatsResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def get_scheduler_statistics(
    org_id: str,
    scheduler_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a specific scheduler."""
    try:
        stats = await get_scheduler_stats(db, org_id, scheduler_id)
        return SchedulerStatsResponse(scheduler_id=scheduler_id, stats=stats)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/organizations/{org_id}/schedulers/{scheduler_id}/runs",
    response_model=SchedulerRunListResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def list_scheduler_run_history(
    org_id: str,
    scheduler_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="Filter by status: pending, running, completed, failed, cancelled, partial"),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List run history for a scheduler."""
    try:
        runs, total = await list_scheduler_runs(
            db, org_id, scheduler_id, skip, limit, status
        )
        return SchedulerRunListResponse(
            items=[SchedulerRunResponse.model_validate(r) for r in runs],
            total=total,
            page=skip // limit + 1 if limit > 0 else 1,
            page_size=limit,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/organizations/{org_id}/schedulers/{scheduler_id}/runs/{run_id}",
    response_model=SchedulerRunResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def get_scheduler_run_detail(
    org_id: str,
    scheduler_id: str,
    run_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific scheduler run."""
    try:
        run = await get_scheduler_run(db, org_id, scheduler_id, run_id)
        return SchedulerRunResponse.model_validate(run)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/organizations/{org_id}/schedulers/{scheduler_id}/runs/{run_id}/logs",
    response_model=SchedulerLogListResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def list_scheduler_run_logs(
    org_id: str,
    scheduler_id: str,
    run_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    level: str | None = Query(None, description="Filter by log level: debug, info, warning, error"),
    data_type: str | None = Query(None, description="Filter by data type: expenses, resources, recommendations"),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List logs for a specific scheduler run."""
    try:
        logs, total = await list_scheduler_logs(
            db, org_id, scheduler_id, run_id, skip, limit, level, data_type
        )
        return SchedulerLogListResponse(
            items=[SchedulerLogResponse.model_validate(l) for l in logs],
            total=total,
            page=skip // limit + 1 if limit > 0 else 1,
            page_size=limit,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/organizations/{org_id}/scheduler-stats",
    response_model=dict[str, Any],
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def get_organization_scheduler_statistics(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get overall scheduler statistics for an organization."""
    stats = await get_organization_scheduler_stats(db, org_id)
    return stats


# ==================== Dead Letter Queue Endpoints ====================

@router.get(
    "/organizations/{org_id}/dead-letter",
    response_model=DeadLetterJobListResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def list_dead_letter_jobs_endpoint(
    org_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="Filter by status: pending, retried, abandoned"),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List dead letter jobs for failed scheduler runs."""
    jobs, total = await list_dead_letter_jobs(db, org_id, skip, limit, status)
    return DeadLetterJobListResponse(
        items=[DeadLetterJobResponse.model_validate(j) for j in jobs],
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )


@router.get(
    "/organizations/{org_id}/dead-letter/{job_id}",
    response_model=DeadLetterJobResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def get_dead_letter_job_endpoint(
    org_id: str,
    job_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific dead letter job."""
    job = await get_dead_letter_job(db, org_id, job_id)
    return DeadLetterJobResponse.model_validate(job)


@router.post(
    "/organizations/{org_id}/dead-letter/{job_id}/retry",
    response_model=RetryDeadLetterJobResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.MANAGE, RBACResourceType.ENTERPRISE))],
)
async def retry_dead_letter_job_endpoint(
    org_id: str,
    job_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Retry a dead letter job."""
    try:
        job, run_id = await retry_dead_letter_job(db, org_id, job_id)
        return RetryDeadLetterJobResponse(
            success=True,
            run_id=run_id,
            message=f"Dead letter job {job_id} queued for retry",
        )
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/organizations/{org_id}/dead-letter/{job_id}",
    status_code=204,
    dependencies=[Depends(require_org_permission(PermissionAction.DELETE, RBACResourceType.ENTERPRISE))],
)
async def abandon_dead_letter_job_endpoint(
    org_id: str,
    job_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Abandon (permanently mark) a dead letter job."""
    try:
        await abandon_dead_letter_job(db, org_id, job_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
