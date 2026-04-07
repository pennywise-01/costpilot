"""Scheduler executor - Handles APScheduler integration and job execution."""

import asyncio
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.expenses.service import get_expense_summary, get_expense_breakdown
from app.recommendations.csp_service import fetch_csp_recommendations
from app.resources.service import _discover_all_resources
from app.scheduler.enums import LogLevel, ScheduleType, SchedulerStatus, TriggerType
from app.scheduler.models import DeadLetterJob, SchedulerConfig, SchedulerLog, SchedulerRun

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def init_scheduler() -> AsyncIOScheduler:
    """Initialize and start the scheduler."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")
    return scheduler


def shutdown_scheduler() -> None:
    """Shutdown the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("APScheduler shutdown")
        _scheduler = None


async def load_schedulers_from_db() -> None:
    """Load all enabled schedulers from database and schedule them."""
    scheduler = get_scheduler()
    
    async with async_session_factory() as session:
        result = await session.execute(
            select(SchedulerConfig).where(SchedulerConfig.is_enabled == True)
        )
        configs = result.scalars().all()
        
        for config in configs:
            await schedule_scheduler_job(config, scheduler)
        
        logger.info(f"Loaded {len(configs)} enabled schedulers from database")


async def schedule_scheduler_job(
    config: SchedulerConfig, scheduler: AsyncIOScheduler | None = None
) -> None:
    """Schedule a single scheduler job."""
    if scheduler is None:
        scheduler = get_scheduler()
    
    job_id = f"scheduler_{config.id}"
    
    # Remove existing job if present
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)
    
    # Don't schedule if disabled or max failures reached
    if not config.is_enabled:
        logger.debug(f"Scheduler {config.id} is disabled, not scheduling")
        return
    
    if config.consecutive_failures >= config.max_consecutive_failures:
        logger.warning(
            f"Scheduler {config.id} has reached max consecutive failures, not scheduling"
        )
        return
    
    # Check date range
    now = datetime.now(timezone.utc)
    if config.end_date and config.end_date < now:
        logger.debug(f"Scheduler {config.id} has passed end date, not scheduling")
        return
    
    # Build trigger based on schedule type
    trigger = None
    if config.schedule_type == ScheduleType.INTERVAL:
        if config.interval_minutes:
            trigger = IntervalTrigger(minutes=config.interval_minutes)
    elif config.schedule_type == ScheduleType.CRON:
        if config.cron_expression:
            trigger = CronTrigger.from_crontab(config.cron_expression)
    elif config.schedule_type == ScheduleType.ONCE:
        if config.start_date and config.start_date > now:
            trigger = DateTrigger(run_date=config.start_date)
    
    if trigger is None:
        logger.error(f"Could not create trigger for scheduler {config.id}")
        return
    
    # Schedule the job
    scheduler.add_job(
        execute_scheduler_job,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
        args=[config.id],
        misfire_grace_time=300,  # 5 minutes grace time
        coalesce=True,  # Coalesce missed jobs into one
    )
    
    logger.info(f"Scheduled job {job_id} with trigger {config.schedule_type}")


async def unschedule_scheduler_job(scheduler_id: str) -> None:
    """Remove a scheduled job."""
    scheduler = get_scheduler()
    job_id = f"scheduler_{scheduler_id}"
    
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)
        logger.info(f"Removed scheduled job {job_id}")


async def execute_scheduler_job(scheduler_id: str, existing_run_id: str | None = None) -> None:
    """Execute a scheduled job.
    
    Args:
        scheduler_id: The scheduler config ID.
        existing_run_id: If provided, use this existing run record instead of creating a new one.
    """
    run_id = existing_run_id or str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        # Get scheduler config
        config = await session.get(SchedulerConfig, scheduler_id)
        if not config:
            logger.error(f"Scheduler config {scheduler_id} not found")
            return

        # Check if should run
        if not config.is_enabled:
            logger.info(f"Scheduler {scheduler_id} is disabled, skipping execution")
            return

        if config.consecutive_failures >= config.max_consecutive_failures:
            logger.warning(
                f"Scheduler {scheduler_id} has reached max failures, skipping execution"
            )
            return

        # Create or fetch run record
        if existing_run_id:
            run = await session.get(SchedulerRun, existing_run_id)
            if not run:
                logger.error(f"Existing run {existing_run_id} not found")
                return
        else:
            run = SchedulerRun(
                id=run_id,
                scheduler_config_id=scheduler_id,
                organization_id=config.organization_id,
                status=SchedulerStatus.RUNNING.value,
                trigger_type=TriggerType.SCHEDULED.value,
            )
            session.add(run)
        await session.commit()

    # Reload config to ensure we have fresh state after session close
    async with async_session_factory() as session:
        config = await session.get(SchedulerConfig, scheduler_id)
        if not config:
            logger.error(f"Scheduler config {scheduler_id} not found after session reopen")
            return

    logger.info(f"Starting scheduled job {scheduler_id}, run {run_id}")

    # Track results
    results = {
        "expenses": {"success": False, "records": 0, "error": None},
        "resources": {"success": False, "records": 0, "error": None},
        "recommendations": {"success": False, "records": 0, "error": None},
    }

    try:
        # Collect expenses
        if config.collect_expenses:
            await _log_run_event_async(
                run_id, LogLevel.INFO, "Starting expenses collection"
            )
            try:
                # Refresh cost cache (this fetches from CSPs and stores in DB)
                from app.cost_cache.service import refresh_cost_cache
                async with async_session_factory() as session:
                    cache_result = await refresh_cost_cache(
                        session, config.organization_id, force=False
                    )

                results["expenses"]["success"] = cache_result.success
                results["expenses"]["records"] = cache_result.accounts_success

                async with async_session_factory() as session:
                    run = await session.get(SchedulerRun, run_id)
                    if run:
                        run.collected_expenses = True
                        if cache_result.success:
                            run.expenses_status = SchedulerStatus.COMPLETED.value
                            run.expenses_records = cache_result.accounts_success
                            await _log_run_event(
                                session,
                                run_id,
                                LogLevel.INFO,
                                f"Cost cache refreshed successfully: {cache_result.accounts_success}/{cache_result.accounts_total} accounts, "
                                f"total=${cache_result.this_month_total:.2f}",
                                data_type="expenses",
                                details={
                                    "accounts_total": cache_result.accounts_total,
                                    "accounts_success": cache_result.accounts_success,
                                    "this_month_total": cache_result.this_month_total,
                                    "forecast": cache_result.forecast_total,
                                },
                            )
                        else:
                            run.expenses_status = SchedulerStatus.FAILED.value
                            await _log_run_event(
                                session,
                                run_id,
                                LogLevel.ERROR,
                                f"Cost cache refresh failed: {cache_result.error_message}",
                                data_type="expenses",
                                details={
                                    "accounts_total": cache_result.accounts_total,
                                    "accounts_failed": cache_result.accounts_failed,
                                    "error": cache_result.error_message,
                                },
                            )
                        await session.commit()
            except Exception as e:
                error_msg = str(e)
                results["expenses"]["error"] = error_msg
                async with async_session_factory() as session:
                    run = await session.get(SchedulerRun, run_id)
                    if run:
                        run.expenses_status = SchedulerStatus.FAILED.value
                        await _log_run_event(
                            session,
                            run_id,
                            LogLevel.ERROR,
                            f"Expenses collection failed: {error_msg}",
                            data_type="expenses",
                            details={"traceback": traceback.format_exc()},
                        )
                        await session.commit()

        # Collect resources
        if config.collect_resources:
            await _log_run_event_async(
                run_id, LogLevel.INFO, "Starting resources collection"
            )
            try:
                resources = await _discover_all_resources(config.organization_id)
                results["resources"]["success"] = True
                results["resources"]["records"] = len(resources)

                async with async_session_factory() as session:
                    run = await session.get(SchedulerRun, run_id)
                    if run:
                        run.collected_resources = True
                        run.resources_status = SchedulerStatus.COMPLETED.value
                        run.resources_records = len(resources)
                        await _log_run_event(
                            session,
                            run_id,
                            LogLevel.INFO,
                            f"Resources collected successfully: {len(resources)} resources",
                            data_type="resources",
                        )
                        await session.commit()
            except Exception as e:
                error_msg = str(e)
                results["resources"]["error"] = error_msg
                async with async_session_factory() as session:
                    run = await session.get(SchedulerRun, run_id)
                    if run:
                        run.resources_status = SchedulerStatus.FAILED.value
                        await _log_run_event(
                            session,
                            run_id,
                            LogLevel.ERROR,
                            f"Resources collection failed: {error_msg}",
                            data_type="resources",
                            details={"traceback": traceback.format_exc()},
                        )
                        await session.commit()

        # Collect recommendations
        if config.collect_recommendations:
            await _log_run_event_async(
                run_id, LogLevel.INFO, "Starting recommendations collection"
            )
            try:
                from app.database import get_mongo_db
                mongo_db = get_mongo_db()
                async with async_session_factory() as session:
                    recommendations = await fetch_csp_recommendations(
                        session, mongo_db, config.organization_id
                    )
                results["recommendations"]["success"] = True
                results["recommendations"]["records"] = len(recommendations)

                async with async_session_factory() as session:
                    run = await session.get(SchedulerRun, run_id)
                    if run:
                        run.collected_recommendations = True
                        run.recommendations_status = SchedulerStatus.COMPLETED.value
                        run.recommendations_records = len(recommendations)
                        await _log_run_event(
                            session,
                            run_id,
                            LogLevel.INFO,
                            f"Recommendations collected successfully: {len(recommendations)} recommendations",
                            data_type="recommendations",
                        )
                        await session.commit()
            except Exception as e:
                error_msg = str(e)
                results["recommendations"]["error"] = error_msg
                async with async_session_factory() as session:
                    run = await session.get(SchedulerRun, run_id)
                    if run:
                        run.recommendations_status = SchedulerStatus.FAILED.value
                        await _log_run_event(
                            session,
                            run_id,
                            LogLevel.ERROR,
                            f"Recommendations collection failed: {error_msg}",
                            data_type="recommendations",
                            details={"traceback": traceback.format_exc()},
                        )
                        await session.commit()

        # Calculate final status and update config
        async with async_session_factory() as session:
            run = await session.get(SchedulerRun, run_id)
            config = await session.get(SchedulerConfig, scheduler_id)
            if not run or not config:
                logger.error(f"Run or config not found when finalizing job {scheduler_id}")
                return

            success_count = sum(1 for r in results.values() if r["success"])
            failure_count = sum(1 for r in results.values() if r["error"])

            if failure_count == 0:
                run.status = SchedulerStatus.COMPLETED.value
                config.consecutive_failures = 0
            elif success_count == 0:
                run.status = SchedulerStatus.FAILED.value
                config.consecutive_failures += 1
            else:
                run.status = SchedulerStatus.PARTIAL.value
                config.consecutive_failures = 0

            # Check if we've reached max failures and need to move to dead letter queue
            moved_to_dead_letter = False
            if config.consecutive_failures >= config.max_consecutive_failures:
                dead_letter = DeadLetterJob(
                    id=str(uuid.uuid4()),
                    scheduler_config_id=config.id,
                    original_run_id=run_id,
                    error_message=run.error_message or "Job failed after multiple attempts",
                    error_traceback=traceback.format_exc() if run.error_details and run.error_details.get("traceback") else None,
                    failure_count=config.consecutive_failures,
                    max_retries=config.max_consecutive_failures,
                    status="pending",
                )
                session.add(dead_letter)
                logger.warning(
                    f"Scheduler {scheduler_id} reached max consecutive failures ({config.consecutive_failures}), "
                    f"moved to dead letter queue as {dead_letter.id}"
                )
                moved_to_dead_letter = True

            # Update timing
            end_time = datetime.now(timezone.utc)
            run.completed_at = end_time
            run.duration_seconds = int((end_time - start_time).total_seconds())
            config.last_run_at = start_time

            await session.commit()
            logger.info(f"Completed scheduled job {scheduler_id}, run {run_id}")

            # Unschedul if moved to dead letter
            if moved_to_dead_letter:
                await unschedule_scheduler_job(scheduler_id)

    except Exception as e:
        # Critical failure - mark as failed
        end_time = datetime.now(timezone.utc)
        moved_to_dead_letter = False
        async with async_session_factory() as session:
            run = await session.get(SchedulerRun, run_id)
            config = await session.get(SchedulerConfig, scheduler_id)
            if run:
                run.status = SchedulerStatus.FAILED.value
                run.completed_at = end_time
                run.duration_seconds = int((end_time - start_time).total_seconds())
                run.error_message = str(e)
                run.error_details = {"traceback": traceback.format_exc()}
            if config:
                config.consecutive_failures += 1
                config.last_run_at = start_time

                # Check if we've reached max failures and need to move to dead letter queue
                if config.consecutive_failures >= config.max_consecutive_failures:
                    dead_letter = DeadLetterJob(
                        id=str(uuid.uuid4()),
                        scheduler_config_id=config.id,
                        original_run_id=run_id,
                        error_message=str(e),
                        error_traceback=traceback.format_exc(),
                        failure_count=config.consecutive_failures,
                        max_retries=config.max_consecutive_failures,
                        status="pending",
                    )
                    session.add(dead_letter)
                    logger.warning(
                        f"Scheduler {scheduler_id} reached max consecutive failures ({config.consecutive_failures}), "
                        f"moved to dead letter queue as {dead_letter.id}"
                    )
                    moved_to_dead_letter = True

            await _log_run_event(
                session,
                run_id,
                LogLevel.ERROR,
                f"Critical failure in scheduled job: {str(e)}",
                details={"traceback": traceback.format_exc()},
            )

            await session.commit()
            logger.exception(f"Critical failure in scheduled job {scheduler_id}")

        # Unschedul if moved to dead letter
        if moved_to_dead_letter:
            await unschedule_scheduler_job(scheduler_id)
        # Reschedule if needed (for one-time jobs or if disabled due to failures)
        else:
            async with async_session_factory() as session:
                config_check = await session.get(SchedulerConfig, scheduler_id)
                if config_check and config_check.is_enabled and config_check.consecutive_failures < config_check.max_consecutive_failures:
                    if config_check.schedule_type != ScheduleType.ONCE:
                        await schedule_scheduler_job(config_check)


async def _log_run_event_async(
    run_id: str,
    level: LogLevel,
    message: str,
    data_type: str | None = None,
    cloud_account_id: str | None = None,
    cloud_account_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log an event for a scheduler run (without requiring an existing session)."""
    async with async_session_factory() as session:
        log_entry = SchedulerLog(
            id=str(uuid.uuid4()),
            scheduler_run_id=run_id,
            level=level.value,
            message=message,
            data_type=data_type,
            cloud_account_id=cloud_account_id,
            cloud_account_name=cloud_account_name,
            details=details,
        )
        session.add(log_entry)
        await session.commit()


async def _log_run_event(
    session: AsyncSession,
    run_id: str,
    level: LogLevel,
    message: str,
    data_type: str | None = None,
    cloud_account_id: str | None = None,
    cloud_account_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log an event for a scheduler run."""
    log_entry = SchedulerLog(
        id=str(uuid.uuid4()),
        scheduler_run_id=run_id,
        level=level.value,
        message=message,
        data_type=data_type,
        cloud_account_id=cloud_account_id,
        cloud_account_name=cloud_account_name,
        details=details,
    )
    session.add(log_entry)
    await session.flush()


async def execute_manual_run(
    config: SchedulerConfig, triggered_by: str | None = None
) -> str:
    """Execute a manual run of a scheduler.

    Returns the run ID.
    """
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        # Create run record
        run = SchedulerRun(
            id=run_id,
            scheduler_config_id=config.id,
            organization_id=config.organization_id,
            status=SchedulerStatus.RUNNING.value,
            trigger_type=TriggerType.MANUAL.value,
            triggered_by=triggered_by,
        )
        session.add(run)
        await session.commit()

        logger.info(f"Starting manual job {config.id}, run {run_id}")

    # Execute the same logic as scheduled job, passing the existing run_id
    asyncio.create_task(_execute_manual_run_async(config.id, run_id, start_time))

    return run_id


async def _execute_manual_run_async(
    config_id: str, run_id: str, start_time: datetime
) -> None:
    """Async execution of manual run.
    
    Args:
        config_id: The scheduler config ID.
        run_id: The existing run record ID to use.
        start_time: When the run started.
    """
    # Reuse the same execution logic as scheduled jobs, passing existing_run_id
    await execute_scheduler_job(config_id, existing_run_id=run_id)
