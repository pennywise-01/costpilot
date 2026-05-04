"""Scheduler service - CRUD operations and business logic."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.scheduler.enums import SchedulerStatus
from app.scheduler.executor import (
    execute_manual_run,
    execute_scheduler_job,
    schedule_scheduler_job,
    unschedule_scheduler_job,
)
from app.scheduler.models import DeadLetterJob, SchedulerConfig, SchedulerLog, SchedulerRun
from app.scheduler.schemas import (
    ManualTriggerResponse,
    SchedulerConfigCreate,
    SchedulerConfigUpdate,
    SchedulerStats,
    ToggleSchedulerResponse,
)
from app.shared.exceptions import BadRequestError, NotFoundError
from app.shared.utils.time import utc_now


async def create_scheduler_config(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: SchedulerConfigCreate,
) -> SchedulerConfig:
    """Create a new scheduler configuration."""
    # Validate at least one data type is selected
    if not any([
        data.collect_expenses,
        data.collect_resources,
        data.collect_recommendations,
    ]):
        raise BadRequestError("At least one data type must be selected for collection")
    
    # Validate schedule configuration
    if data.schedule_type.value == "interval" and not data.interval_minutes:
        raise BadRequestError("Interval minutes is required for interval schedule type")
    
    if data.schedule_type.value == "cron" and not data.cron_expression:
        raise BadRequestError("Cron expression is required for cron schedule type")
    
    # Create config
    config = SchedulerConfig(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        created_by=user_id,
        name=data.name,
        description=data.description,
        collect_expenses=data.collect_expenses,
        collect_resources=data.collect_resources,
        collect_recommendations=data.collect_recommendations,
        schedule_type=data.schedule_type.value,
        interval_minutes=data.interval_minutes,
        cron_expression=data.cron_expression,
        timezone=data.timezone,
        start_date=data.start_date,
        end_date=data.end_date,
        is_enabled=data.is_enabled,
        max_consecutive_failures=data.max_consecutive_failures,
        consecutive_failures=0,
    )
    
    db.add(config)
    await db.flush()
    
    # Schedule the job if enabled
    if config.is_enabled:
        await schedule_scheduler_job(config)
    
    return config


async def list_scheduler_configs(
    db: AsyncSession,
    org_id: str,
    skip: int = 0,
    limit: int = 100,
    include_stats: bool = False,
) -> tuple[list[SchedulerConfig], int]:
    """List scheduler configurations for an organization.
    
    Returns tuple of (configs, total_count).
    """
    # Get total count
    count_result = await db.execute(
        select(func.count(SchedulerConfig.id)).where(
            SchedulerConfig.organization_id == org_id
        )
    )
    total = count_result.scalar() or 0
    
    # Get configs
    result = await db.execute(
        select(SchedulerConfig)
        .where(SchedulerConfig.organization_id == org_id)
        .order_by(desc(SchedulerConfig.created_at))
        .offset(skip)
        .limit(limit)
    )
    configs = list(result.scalars().all())
    
    return configs, total


async def get_scheduler_config(
    db: AsyncSession, org_id: str, config_id: str
) -> SchedulerConfig:
    """Get a scheduler configuration by ID."""
    result = await db.execute(
        select(SchedulerConfig).where(
            SchedulerConfig.id == config_id,
            SchedulerConfig.organization_id == org_id,
        ).limit(1)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise NotFoundError(f"Scheduler config '{config_id}' not found")
    
    return config


async def update_scheduler_config(
    db: AsyncSession,
    org_id: str,
    config_id: str,
    data: SchedulerConfigUpdate,
) -> SchedulerConfig:
    """Update a scheduler configuration."""
    config = await get_scheduler_config(db, org_id, config_id)
    
    # Validate at least one data type is selected if updating data types
    if (
        data.collect_expenses is not None
        or data.collect_resources is not None
        or data.collect_recommendations is not None
    ):
        new_expenses = data.collect_expenses if data.collect_expenses is not None else config.collect_expenses
        new_resources = data.collect_resources if data.collect_resources is not None else config.collect_resources
        new_recommendations = data.collect_recommendations if data.collect_recommendations is not None else config.collect_recommendations
        
        if not any([new_expenses, new_resources, new_recommendations]):
            raise BadRequestError("At least one data type must be selected for collection")
    
    # Validate schedule configuration if updating schedule
    if data.schedule_type is not None:
        new_schedule_type = data.schedule_type.value
        
        if new_schedule_type == "interval":
            new_interval = data.interval_minutes if data.interval_minutes is not None else config.interval_minutes
            if not new_interval:
                raise BadRequestError("Interval minutes is required for interval schedule type")
        
        elif new_schedule_type == "cron":
            new_cron = data.cron_expression if data.cron_expression is not None else config.cron_expression
            if not new_cron:
                raise BadRequestError("Cron expression is required for cron schedule type")
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "schedule_type" and value is not None:
            value = value.value  # Convert enum to string
        setattr(config, field, value)
    
    await db.flush()
    
    # Reschedule job if schedule-related fields changed
    schedule_fields = {"schedule_type", "interval_minutes", "cron_expression", "start_date", "end_date", "is_enabled"}
    if any(field in update_data for field in schedule_fields):
        if config.is_enabled:
            await schedule_scheduler_job(config)
        else:
            await unschedule_scheduler_job(config.id)
    
    return config


async def delete_scheduler_config(
    db: AsyncSession, org_id: str, config_id: str
) -> None:
    """Delete a scheduler configuration."""
    config = await get_scheduler_config(db, org_id, config_id)
    
    # Unschedule the job
    await unschedule_scheduler_job(config.id)
    
    # Delete the config (cascade will handle runs and logs)
    await db.delete(config)


async def toggle_scheduler(
    db: AsyncSession,
    org_id: str,
    config_id: str,
    is_enabled: bool,
) -> ToggleSchedulerResponse:
    """Enable or disable a scheduler."""
    config = await get_scheduler_config(db, org_id, config_id)
    
    config.is_enabled = is_enabled
    
    if is_enabled:
        # Reset consecutive failures when enabling
        config.consecutive_failures = 0
        await schedule_scheduler_job(config)
        message = f"Scheduler '{config.name}' enabled"
    else:
        await unschedule_scheduler_job(config.id)
        message = f"Scheduler '{config.name}' disabled"
    
    await db.flush()
    
    return ToggleSchedulerResponse(
        success=True,
        is_enabled=is_enabled,
        message=message,
    )


async def trigger_scheduler_manual(
    db: AsyncSession,
    org_id: str,
    config_id: str,
    user_id: str,
    override_expenses: bool | None = None,
    override_resources: bool | None = None,
    override_recommendations: bool | None = None,
) -> ManualTriggerResponse:
    """Manually trigger a scheduler run."""
    config = await get_scheduler_config(db, org_id, config_id)
    
    if not config.is_enabled:
        return ManualTriggerResponse(
            success=False,
            run_id=None,
            message=f"Scheduler '{config.name}' is disabled. Enable it first.",
        )
    
    # Create temporary overrides if provided
    original_values = {}
    if override_expenses is not None:
        original_values["collect_expenses"] = config.collect_expenses
        config.collect_expenses = override_expenses
    if override_resources is not None:
        original_values["collect_resources"] = config.collect_resources
        config.collect_resources = override_resources
    if override_recommendations is not None:
        original_values["collect_recommendations"] = config.collect_recommendations
        config.collect_recommendations = override_recommendations
    
    try:
        run_id = await execute_manual_run(config, triggered_by=user_id)
        
        return ManualTriggerResponse(
            success=True,
            run_id=run_id,
            message=f"Manual run started for scheduler '{config.name}'",
        )
    finally:
        # Restore original values
        for field, value in original_values.items():
            setattr(config, field, value)


async def get_scheduler_stats(
    db: AsyncSession, org_id: str, config_id: str
) -> SchedulerStats:
    """Get statistics for a scheduler."""
    config = await get_scheduler_config(db, org_id, config_id)
    
    # Get run counts
    total_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.scheduler_config_id == config_id
        )
    )
    total_runs = total_result.scalar() or 0
    
    success_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.scheduler_config_id == config_id,
            SchedulerRun.status == SchedulerStatus.COMPLETED.value,
        )
    )
    successful_runs = success_result.scalar() or 0
    
    failed_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.scheduler_config_id == config_id,
            SchedulerRun.status == SchedulerStatus.FAILED.value,
        )
    )
    failed_runs = failed_result.scalar() or 0
    
    partial_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.scheduler_config_id == config_id,
            SchedulerRun.status == SchedulerStatus.PARTIAL.value,
        )
    )
    partial_runs = partial_result.scalar() or 0
    
    # Get average duration
    avg_result = await db.execute(
        select(func.avg(SchedulerRun.duration_seconds)).where(
            SchedulerRun.scheduler_config_id == config_id,
            SchedulerRun.duration_seconds.isnot(None),
        )
    )
    avg_duration = avg_result.scalar()
    
    return SchedulerStats(
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        partial_runs=partial_runs,
        avg_duration_seconds=float(avg_duration) if avg_duration else None,
        last_run_status=config.last_run_at and "completed",  # Simplified
        last_run_at=config.last_run_at,
    )


async def list_scheduler_runs(
    db: AsyncSession,
    org_id: str,
    config_id: str,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> tuple[list[SchedulerRun], int]:
    """List runs for a scheduler.
    
    Returns tuple of (runs, total_count).
    """
    # Verify config exists and belongs to org
    await get_scheduler_config(db, org_id, config_id)
    
    # Build query
    query = select(SchedulerRun).where(
        SchedulerRun.scheduler_config_id == config_id,
        SchedulerRun.organization_id == org_id,
    )
    
    if status:
        query = query.where(SchedulerRun.status == status)
    
    # Get total count
    count_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.scheduler_config_id == config_id,
            SchedulerRun.organization_id == org_id,
        )
    )
    total = count_result.scalar() or 0
    
    # Get runs
    result = await db.execute(
        query.order_by(desc(SchedulerRun.started_at)).offset(skip).limit(limit)
    )
    runs = list(result.scalars().all())
    
    return runs, total


async def get_scheduler_run(
    db: AsyncSession, org_id: str, config_id: str, run_id: str
) -> SchedulerRun:
    """Get a specific scheduler run."""
    # Verify config exists and belongs to org
    await get_scheduler_config(db, org_id, config_id)
    
    result = await db.execute(
        select(SchedulerRun).where(
            SchedulerRun.id == run_id,
            SchedulerRun.scheduler_config_id == config_id,
            SchedulerRun.organization_id == org_id,
        ).limit(1)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise NotFoundError(f"Scheduler run '{run_id}' not found")
    
    return run


async def list_scheduler_logs(
    db: AsyncSession,
    org_id: str,
    config_id: str,
    run_id: str,
    skip: int = 0,
    limit: int = 100,
    level: str | None = None,
    data_type: str | None = None,
) -> tuple[list[SchedulerLog], int]:
    """List logs for a scheduler run.
    
    Returns tuple of (logs, total_count).
    """
    # Verify run exists and belongs to org
    await get_scheduler_run(db, org_id, config_id, run_id)
    
    # Build query
    query = select(SchedulerLog).where(
        SchedulerLog.scheduler_run_id == run_id,
    )
    
    if level:
        query = query.where(SchedulerLog.level == level)
    
    if data_type:
        query = query.where(SchedulerLog.data_type == data_type)
    
    # Get total count
    count_result = await db.execute(
        select(func.count(SchedulerLog.id)).where(
            SchedulerLog.scheduler_run_id == run_id,
        )
    )
    total = count_result.scalar() or 0
    
    # Get logs
    result = await db.execute(
        query.order_by(SchedulerLog.logged_at).offset(skip).limit(limit)
    )
    logs = list(result.scalars().all())
    
    return logs, total


async def get_organization_scheduler_stats(
    db: AsyncSession, org_id: str
) -> dict[str, Any]:
    """Get overall scheduler statistics for an organization."""
    # Total schedulers
    total_result = await db.execute(
        select(func.count(SchedulerConfig.id)).where(
            SchedulerConfig.organization_id == org_id
        )
    )
    total_schedulers = total_result.scalar() or 0
    
    # Active schedulers
    active_result = await db.execute(
        select(func.count(SchedulerConfig.id)).where(
            SchedulerConfig.organization_id == org_id,
            SchedulerConfig.is_enabled == True,
        )
    )
    active_schedulers = active_result.scalar() or 0
    
    # Today's runs - use aware datetime
    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_runs_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.organization_id == org_id,
            SchedulerRun.started_at >= today_start,
        )
    )
    total_runs_today = today_runs_result.scalar() or 0
    
    # Today's successful runs
    today_success_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.organization_id == org_id,
            SchedulerRun.started_at >= today_start,
            SchedulerRun.status == SchedulerStatus.COMPLETED.value,
        )
    )
    successful_runs_today = today_success_result.scalar() or 0
    
    # Today's failed runs
    today_failed_result = await db.execute(
        select(func.count(SchedulerRun.id)).where(
            SchedulerRun.organization_id == org_id,
            SchedulerRun.started_at >= today_start,
            SchedulerRun.status == SchedulerStatus.FAILED.value,
        )
    )
    failed_runs_today = today_failed_result.scalar() or 0
    
    return {
        "total_schedulers": total_schedulers,
        "active_schedulers": active_schedulers,
        "inactive_schedulers": total_schedulers - active_schedulers,
        "total_runs_today": total_runs_today,
        "successful_runs_today": successful_runs_today,
        "failed_runs_today": failed_runs_today,
        "upcoming_runs": [],  # Would need to query APScheduler for this
    }


# ==================== Dead Letter Queue Service Functions ====================

async def list_dead_letter_jobs(
    db: AsyncSession,
    org_id: str,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> tuple[list[DeadLetterJob], int]:
    """List dead letter jobs for an organization.

    Returns tuple of (jobs, total_count).
    """
    # Build base query joining with scheduler_configs to filter by org
    query = (
        select(DeadLetterJob)
        .join(SchedulerConfig, DeadLetterJob.scheduler_config_id == SchedulerConfig.id)
        .where(SchedulerConfig.organization_id == org_id)
    )

    if status:
        query = query.where(DeadLetterJob.status == status)

    # Get total count
    count_result = await db.execute(
        select(func.count(DeadLetterJob.id))
        .join(SchedulerConfig, DeadLetterJob.scheduler_config_id == SchedulerConfig.id)
        .where(SchedulerConfig.organization_id == org_id)
    )
    total = count_result.scalar() or 0

    # Get jobs
    result = await db.execute(
        query.order_by(desc(DeadLetterJob.created_at)).offset(skip).limit(limit)
    )
    jobs = list(result.scalars().all())

    return jobs, total


async def get_dead_letter_job(
    db: AsyncSession, org_id: str, job_id: str
) -> DeadLetterJob:
    """Get a specific dead letter job."""
    result = await db.execute(
        select(DeadLetterJob)
        .join(SchedulerConfig, DeadLetterJob.scheduler_config_id == SchedulerConfig.id)
        .where(
            DeadLetterJob.id == job_id,
            SchedulerConfig.organization_id == org_id,
        ).limit(1)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError(f"Dead letter job '{job_id}' not found")

    return job


async def retry_dead_letter_job(
    db: AsyncSession, org_id: str, job_id: str
) -> tuple[DeadLetterJob, str | None]:
    """Retry a dead letter job.

    Returns tuple of (updated_dead_letter_job, new_run_id_or_none).
    """
    job = await get_dead_letter_job(db, org_id, job_id)

    if job.status == "abandoned":
        raise BadRequestError("Cannot retry an abandoned dead letter job")

    # Get the scheduler config
    config = await db.get(SchedulerConfig, job.scheduler_config_id)
    if not config:
        raise NotFoundError(f"Associated scheduler config '{job.scheduler_config_id}' not found")

    # Reset failure count on the config so it can run again
    config.consecutive_failures = 0
    await db.flush()

    # Create a new run for the retry
    run_id = str(uuid.uuid4())
    run = SchedulerRun(
        id=run_id,
        scheduler_config_id=config.id,
        organization_id=config.organization_id,
        status=SchedulerStatus.RUNNING.value,
    )
    db.add(run)
    await db.commit()

    # Update dead letter job status
    from app.shared.utils.time import utc_now
    job.status = "retried"
    job.last_retried_at = utc_now()
    await db.flush()

    # Execute the job asynchronously
    import asyncio
    asyncio.create_task(execute_scheduler_job(config.id, existing_run_id=run_id))

    return job, run_id


async def abandon_dead_letter_job(
    db: AsyncSession, org_id: str, job_id: str
) -> DeadLetterJob:
    """Abandon (permanently mark) a dead letter job."""
    job = await get_dead_letter_job(db, org_id, job_id)

    job.status = "abandoned"
    await db.flush()

    return job
