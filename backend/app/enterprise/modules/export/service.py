"""Data Export service layer for creating and managing exports."""

import csv
import io
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.enterprise.modules.export.enums import ExportFormat, ExportDataType, ExportStatus
from app.enterprise.modules.export.models import ExportJob, ExportTemplate, ScheduledExport
from app.enterprise.modules.export.schemas import (
    ExportTemplateCreate,
    ExportTemplateUpdate,
    ExportJobCreate,
    ScheduledExportCreate,
    ScheduledExportUpdate,
    ExportColumn,
)
from app.shared.exceptions import NotFoundError, BadRequestError
from app.shared.utils.time import utc_now


EXPORT_STORAGE_DIR_NAME = "costpilot_exports"


def get_export_storage_dir() -> Path:
    """Return the dedicated temp directory used for export files."""
    storage_dir = Path(tempfile.gettempdir()) / EXPORT_STORAGE_DIR_NAME
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def is_export_file_path_allowed(file_path: str | None) -> bool:
    """Ensure export file paths resolve inside the dedicated export directory."""
    if not file_path:
        return False

    try:
        storage_dir = get_export_storage_dir().resolve()
        candidate = Path(file_path).resolve()
        candidate.relative_to(storage_dir)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


# ============== Export Data Fetchers ==============

def _coerce_created_at(value: Any) -> str | None:
    """Normalize timestamp-like values to ISO strings for exports."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value).isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _sort_rows(rows: list[dict], sort_by: str | None, sort_order: str | None) -> list[dict]:
    """Apply stable in-memory sorting for export rows."""
    if not rows:
        return rows

    sort_key = sort_by or ""
    if not sort_key:
        return rows

    if sort_key not in rows[0]:
        return rows

    reverse = sort_order != "asc"

    def key_fn(row: dict):
        value = row.get(sort_key)
        if value is None:
            return (1, "")
        if isinstance(value, str):
            return (0, value.lower())
        return (0, value)

    try:
        return sorted(rows, key=key_fn, reverse=reverse)
    except TypeError:
        return sorted(rows, key=lambda row: str(row.get(sort_key, "")), reverse=reverse)

async def fetch_expense_data(
    db: AsyncSession,
    org_id: str,
    filters: dict,
    date_range_start: datetime | None,
    date_range_end: datetime | None,
    sort_by: str | None,
    sort_order: str | None,
) -> list[dict]:
    """Fetch expense data for export."""
    from app.database import get_mongo_db
    from app.expenses.service import get_clean_expenses

    mongo_db = get_mongo_db()
    rows: list[dict] = []

    offset = 0
    limit = 500
    while True:
        expenses = await get_clean_expenses(mongo_db, org_id, limit=limit, offset=offset)
        if not expenses:
            break

        for expense in expenses:
            rows.append(
                {
                    "id": expense.resource_id,
                    "date": None,
                    "amount": float(expense.cost or 0),
                    "currency": "USD",
                    "cloud_account_id": expense.cloud_account_id,
                    "resource_id": expense.resource_id,
                    "service": expense.resource_name,
                    "region": expense.region,
                    "tags": {},
                }
            )

        if len(expenses) < limit:
            break
        offset += limit

    if sort_by is None:
        sort_by = "amount"
        sort_order = sort_order or "desc"

    return _sort_rows(rows, sort_by, sort_order)


async def fetch_resource_data(
    db: AsyncSession,
    org_id: str,
    filters: dict,
    date_range_start: datetime | None,
    date_range_end: datetime | None,
    sort_by: str | None,
    sort_order: str | None,
) -> list[dict]:
    """Fetch resource data for export."""
    from app.database import get_mongo_db
    from app.resources.service import list_resources

    mongo_db = get_mongo_db()
    rows: list[dict] = []

    query_filters: dict[str, Any] = {}
    if isinstance(filters, dict):
        for key in ("cloud_type", "region", "resource_type", "cloud_account_id"):
            value = filters.get(key)
            if value:
                query_filters[key] = value

    offset = 0
    limit = 500
    while True:
        response = await list_resources(
            mongo_db,
            org_id,
            limit=limit,
            offset=offset,
            filters=query_filters or None,
        )
        resources = response.resources
        if not resources:
            break

        for resource in resources:
            created_at = _coerce_created_at(resource.first_seen)
            if date_range_start and created_at:
                if created_at < date_range_start.isoformat():
                    continue
            if date_range_end and created_at:
                if created_at > date_range_end.isoformat():
                    continue

            rows.append(
                {
                    "id": resource.id,
                    "name": resource.name,
                    "resource_type": resource.resource_type,
                    "cloud_type": resource.cloud_type,
                    "cloud_account_id": resource.cloud_account_id,
                    "region": resource.region,
                    "status": "active" if resource.active else "inactive",
                    "created_at": created_at,
                    "tags": resource.tags,
                }
            )

        if len(resources) < limit:
            break
        offset += limit

    if sort_by is None:
        sort_by = "created_at"
        sort_order = sort_order or "desc"

    return _sort_rows(rows, sort_by, sort_order)


async def fetch_recommendation_data(
    db: AsyncSession,
    org_id: str,
    filters: dict,
    date_range_start: datetime | None,
    date_range_end: datetime | None,
    sort_by: str | None,
    sort_order: str | None,
) -> list[dict]:
    """Fetch recommendation data for export."""
    from app.database import get_mongo_db
    from app.recommendations.service import get_recommendations_overview

    mongo_db = get_mongo_db()
    overview = await get_recommendations_overview(mongo_db, org_id, db=db)

    rows: list[dict] = []
    for rec in overview.recommendations:
        if rec.items:
            for idx, item in enumerate(rec.items):
                created_at = _coerce_created_at(item.get("created_at"))
                estimated_saving = item.get("saving")
                if estimated_saving is None:
                    if rec.count > 0:
                        estimated_saving = rec.saving / rec.count
                    else:
                        estimated_saving = rec.saving

                rows.append(
                    {
                        "id": item.get("id") or f"{rec.type}-{idx}",
                        "title": item.get("title") or item.get("name") or rec.name,
                        "description": item.get("description") or rec.description,
                        "recommendation_type": rec.type,
                        "severity": item.get("severity") or "medium",
                        "status": "dismissed" if item.get("dismissed") else "open",
                        "potential_savings": float(estimated_saving or 0),
                        "currency": item.get("currency") or "USD",
                        "created_at": created_at,
                    }
                )
        else:
            rows.append(
                {
                    "id": rec.type,
                    "title": rec.name,
                    "description": rec.description,
                    "recommendation_type": rec.type,
                    "severity": "medium",
                    "status": "open",
                    "potential_savings": float(rec.saving or 0),
                    "currency": "USD",
                    "created_at": None,
                }
            )

    if sort_by is None:
        sort_by = "potential_savings"
        sort_order = sort_order or "desc"

    return _sort_rows(rows, sort_by, sort_order)


# ============== Format Handlers ==============

def format_data_as_csv(data: list[dict], columns: list[ExportColumn]) -> str:
    """Format data as CSV string."""
    if not data:
        return ""
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    headers = [col.label for col in columns] if columns else list(data[0].keys())
    writer.writerow(headers)
    
    # Write data rows
    for row in data:
        if columns:
            row_data = [str(row.get(col.name, "")) for col in columns]
        else:
            row_data = [str(v) for v in row.values()]
        writer.writerow(row_data)
    
    return output.getvalue()


def format_data_as_json(data: list[dict]) -> str:
    """Format data as JSON string."""
    return json.dumps(data, indent=2, default=str)


def format_data_as_parquet(data: list[dict]) -> bytes:
    """Format data as Parquet bytes."""
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_parquet(output, index=False)
    return output.getvalue()


def format_data_as_excel(data: list[dict], sheet_name: str = "Data") -> bytes:
    """Format data as Excel bytes."""
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, sheet_name=sheet_name, index=False)
    return output.getvalue()


# ============== Streaming Export Generators ==============

async def stream_csv_data(query_func, limit: int = 5000):
    """Stream CSV data using pagination to avoid loading everything into memory."""
    import csv
    import io

    offset = 0
    while True:
        batch = await query_func(limit=limit, offset=offset)
        if not batch:
            break

        for i, row in enumerate(batch):
            if i == 0:
                # Write header
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=list(row.keys()))
                writer.writeheader()
                yield output.getvalue().encode("utf-8")

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=list(row.keys()))
            writer.writerow(row)
            yield output.getvalue().encode("utf-8")

        if len(batch) < limit:
            break
        offset += limit


async def stream_json_data(query_func, limit: int = 5000):
    """Stream JSON data as NDJSON (newline-delimited JSON)."""
    import json

    offset = 0
    yield b"["
    first = True
    while True:
        batch = await query_func(limit=limit, offset=offset)
        if not batch:
            break

        for row in batch:
            if first:
                first = False
            else:
                yield b","
            yield json.dumps(row).encode("utf-8")

        if len(batch) < limit:
            break
        offset += limit
    yield b"]"


# ============== Export Job Service ==============

async def create_export_job(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: ExportJobCreate,
) -> ExportJob:
    """Create a new export job."""
    if data.template_id:
        await get_export_template(db, org_id, data.template_id)

    job = ExportJob(
        organization_id=org_id,
        template_id=data.template_id,
        name=data.name,
        data_type=data.data_type,
        format=data.format,
        columns=[col.model_dump() for col in data.columns],
        filters=data.filters,
        date_range_start=data.date_range_start,
        date_range_end=data.date_range_end,
        group_by=data.group_by,
        sort_by=data.sort_by,
        sort_order=data.sort_order,
        status=ExportStatus.PENDING,
        created_by=user_id,
        delivery_config=data.delivery_config.model_dump() if data.delivery_config else None,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def get_export_job(db: AsyncSession, org_id: str, job_id: str) -> ExportJob:
    """Get an export job by ID."""
    result = await db.execute(
        select(ExportJob).where(
            ExportJob.id == job_id,
            ExportJob.organization_id == org_id,
            ExportJob.deleted_at.is_(None),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("Export job not found")
    return job


async def list_export_jobs(
    db: AsyncSession,
    org_id: str,
    page: int = 1,
    limit: int = 20,
    status: ExportStatus | None = None,
    data_type: ExportDataType | None = None,
) -> dict[str, Any]:
    """List export jobs for an organization."""
    stmt = select(ExportJob).where(
        ExportJob.organization_id == org_id,
        ExportJob.deleted_at.is_(None),
    )
    
    if status:
        stmt = stmt.where(ExportJob.status == status)
    if data_type:
        stmt = stmt.where(ExportJob.data_type == data_type)
    
    # Get total count
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()
    
    # Apply pagination
    stmt = stmt.order_by(desc(ExportJob.created_at))
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    
    pages = (total + limit - 1) // limit
    
    return {
        "items": list(jobs),
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


async def execute_export_job(
    db: AsyncSession,
    org_id: str,
    job_id: str,
) -> ExportJob:
    """Execute an export job and generate the file."""
    job = await get_export_job(db, org_id, job_id)

    # Update status to processing
    job.status = ExportStatus.PROCESSING
    job.started_at = utc_now()
    job.current_step = "fetching_data"
    job.progress_percent = 10.0
    await db.flush()

    try:
        # Fetch data based on type
        if job.data_type == ExportDataType.EXPENSES:
            data = await fetch_expense_data(
                db, job.organization_id, job.filters,
                job.date_range_start, job.date_range_end,
                job.sort_by, job.sort_order,
            )
        elif job.data_type == ExportDataType.RESOURCES:
            data = await fetch_resource_data(
                db, job.organization_id, job.filters,
                job.date_range_start, job.date_range_end,
                job.sort_by, job.sort_order,
            )
        elif job.data_type == ExportDataType.RECOMMENDATIONS:
            data = await fetch_recommendation_data(
                db, job.organization_id, job.filters,
                job.date_range_start, job.date_range_end,
                job.sort_by, job.sort_order,
            )
        else:
            raise BadRequestError(f"Unsupported data type: {job.data_type}")

        job.total_records = len(data)
        job.current_step = "processing"
        job.progress_percent = 30.0
        job.record_count = len(data)
        await db.flush()

        # Format data based on export format
        columns = [ExportColumn(**col) for col in job.columns] if job.columns else None

        job.current_step = "writing_file"
        job.progress_percent = 70.0
        await db.flush()

        if job.format == ExportFormat.CSV:
            content = format_data_as_csv(data, columns)
            file_ext = "csv"
            file_content = content.encode("utf-8")
        elif job.format == ExportFormat.JSON:
            content = format_data_as_json(data)
            file_ext = "json"
            file_content = content.encode("utf-8")
        elif job.format == ExportFormat.PARQUET:
            file_ext = "parquet"
            file_content = format_data_as_parquet(data)
        elif job.format == ExportFormat.EXCEL:
            file_ext = "xlsx"
            file_content = format_data_as_excel(data)
        else:
            raise BadRequestError(f"Unsupported format: {job.format}")

        # Save file to dedicated temp export directory
        filename = f"export_{job.id}_{job.data_type}_{utc_now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
        storage_dir = get_export_storage_dir()
        file_path = storage_dir / filename

        with open(file_path, "wb") as f:
            f.write(file_content)

        job.processed_records = len(data)
        job.file_size_bytes = len(file_content)
        job.file_path = str(file_path)
        job.file_url = (
            f"/api/v1/enterprise/organizations/{job.organization_id}/exports/{job.id}/download"
        )
        job.status = ExportStatus.COMPLETED
        job.completed_at = utc_now()
        job.expires_at = utc_now() + timedelta(days=7)
        job.progress_percent = 100.0
        job.current_step = "complete"

        # Handle cloud storage delivery if configured
        if job.delivery_config:
            await deliver_export_file(job, file_content, filename)

    except Exception as e:
        job.status = ExportStatus.FAILED
        job.error_message = str(e)
        job.progress_percent = 0.0
        job.current_step = "failed"

    await db.flush()
    await db.refresh(job)
    return job


async def deliver_export_file(
    job: ExportJob,
    file_content: bytes,
    filename: str,
) -> None:
    """Deliver export file to configured destination."""
    if not job.delivery_config:
        return
    
    method = job.delivery_config.get("method")
    
    if method == "s3":
        await upload_to_s3(job.delivery_config, file_content, filename)
    elif method == "gcs":
        await upload_to_gcs(job.delivery_config, file_content, filename)
    elif method == "azure_blob":
        await upload_to_azure(job.delivery_config, file_content, filename)
    elif method == "email":
        await send_export_email(job.delivery_config, file_content, filename, job)


async def upload_to_s3(
    config: dict,
    file_content: bytes,
    filename: str,
) -> str:
    """Upload file to AWS S3."""
    import boto3
    
    s3 = boto3.client(
        "s3",
        region_name=config["region"],
        aws_access_key_id=config.get("access_key_id"),
        aws_secret_access_key=config.get("secret_access_key"),
    )
    
    key = f"{config.get('prefix', '')}{filename}"
    s3.put_object(
        Bucket=config["bucket"],
        Key=key,
        Body=file_content,
    )
    
    return f"s3://{config['bucket']}/{key}"


async def upload_to_gcs(
    config: dict,
    file_content: bytes,
    filename: str,
) -> str:
    """Upload file to Google Cloud Storage."""
    from google.cloud import storage
    
    client = storage.Client()
    bucket = client.bucket(config["bucket"])
    blob = bucket.blob(f"{config.get('prefix', '')}{filename}")
    blob.upload_from_string(file_content)
    
    return f"gs://{config['bucket']}/{blob.name}"


async def upload_to_azure(
    config: dict,
    file_content: bytes,
    filename: str,
) -> str:
    """Upload file to Azure Blob Storage."""
    from azure.storage.blob import BlobServiceClient
    
    blob_service = BlobServiceClient.from_connection_string(
        config.get("connection_string")
    )
    blob_client = blob_service.get_blob_client(
        container=config["container"],
        blob=f"{config.get('prefix', '')}{filename}",
    )
    blob_client.upload_blob(file_content, overwrite=True)
    
    return blob_client.url


async def send_export_email(
    config: dict,
    file_content: bytes,
    filename: str,
    job: ExportJob,
) -> None:
    """Send export file via email."""
    # Implementation would use the notification service
    # This is a placeholder
    pass


# ============== Export Template Service ==============

async def create_export_template(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: ExportTemplateCreate,
) -> ExportTemplate:
    """Create a new export template."""
    template = ExportTemplate(
        organization_id=org_id,
        name=data.name,
        description=data.description,
        data_type=data.data_type,
        format=data.format,
        columns=[col.model_dump() for col in data.columns],
        filters=data.filters,
        date_range_days=data.date_range_days,
        group_by=data.group_by,
        sort_by=data.sort_by,
        sort_order=data.sort_order,
        created_by=user_id,
        is_public=data.is_public,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


async def get_export_template(db: AsyncSession, org_id: str, template_id: str) -> ExportTemplate:
    """Get an export template by ID."""
    result = await db.execute(
        select(ExportTemplate).where(
            ExportTemplate.id == template_id,
            ExportTemplate.organization_id == org_id,
            ExportTemplate.deleted_at.is_(None),
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("Export template not found")
    return template


async def list_export_templates(
    db: AsyncSession,
    org_id: str,
    data_type: ExportDataType | None = None,
) -> list[ExportTemplate]:
    """List export templates for an organization."""
    stmt = select(ExportTemplate).where(
        ExportTemplate.organization_id == org_id,
        ExportTemplate.deleted_at.is_(None),
    )
    
    if data_type:
        stmt = stmt.where(ExportTemplate.data_type == data_type)
    
    stmt = stmt.order_by(desc(ExportTemplate.created_at))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_export_template(
    db: AsyncSession,
    org_id: str,
    template_id: str,
    data: ExportTemplateUpdate,
) -> ExportTemplate:
    """Update an export template."""
    template = await get_export_template(db, org_id, template_id)
    
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "columns" and value is not None:
            value = [col.model_dump() if isinstance(col, ExportColumn) else col for col in value]
        setattr(template, field, value)
    
    await db.flush()
    await db.refresh(template)
    return template


async def delete_export_template(db: AsyncSession, org_id: str, template_id: str) -> None:
    """Delete an export template (soft delete)."""
    template = await get_export_template(db, org_id, template_id)
    template.deleted_at = utc_now()
    await db.flush()


# ============== Scheduled Export Service ==============

async def create_scheduled_export(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: ScheduledExportCreate,
) -> ScheduledExport:
    """Create a new scheduled export."""
    # Validate template exists in the same organization
    await get_export_template(db, org_id, data.template_id)
    
    # Calculate next run time
    from croniter import croniter
    next_run = croniter(data.cron_expression, utc_now()).get_next(datetime)
    
    scheduled = ScheduledExport(
        organization_id=org_id,
        template_id=data.template_id,
        name=data.name,
        cron_expression=data.cron_expression,
        timezone=data.timezone,
        delivery_config=data.delivery_config.model_dump(),
        is_active=data.is_active,
        next_run_at=next_run,
        created_by=user_id,
    )
    db.add(scheduled)
    await db.flush()
    await db.refresh(scheduled)
    return scheduled


async def list_scheduled_exports(
    db: AsyncSession,
    org_id: str,
) -> list[ScheduledExport]:
    """List scheduled exports for an organization."""
    stmt = select(ScheduledExport).where(
        ScheduledExport.organization_id == org_id,
        ScheduledExport.deleted_at.is_(None),
    ).order_by(desc(ScheduledExport.created_at))
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_scheduled_export(
    db: AsyncSession,
    org_id: str,
    scheduled_id: str,
    data: ScheduledExportUpdate,
) -> ScheduledExport:
    """Update a scheduled export."""
    result = await db.execute(
        select(ScheduledExport).where(
            ScheduledExport.id == scheduled_id,
            ScheduledExport.organization_id == org_id,
            ScheduledExport.deleted_at.is_(None),
        )
    )
    scheduled = result.scalar_one_or_none()
    if not scheduled:
        raise NotFoundError("Scheduled export not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "delivery_config" and value is not None:
            value = value.model_dump()
        setattr(scheduled, field, value)
    
    # Recalculate next run if cron changed
    if data.cron_expression:
        from croniter import croniter
        scheduled.next_run_at = croniter(
            data.cron_expression, utc_now()
        ).get_next(datetime)
    
    await db.flush()
    await db.refresh(scheduled)
    return scheduled


async def delete_scheduled_export(db: AsyncSession, org_id: str, scheduled_id: str) -> None:
    """Delete a scheduled export."""
    result = await db.execute(
        select(ScheduledExport).where(
            ScheduledExport.id == scheduled_id,
            ScheduledExport.organization_id == org_id,
            ScheduledExport.deleted_at.is_(None),
        )
    )
    scheduled = result.scalar_one_or_none()
    if not scheduled:
        raise NotFoundError("Scheduled export not found")

    scheduled.deleted_at = utc_now()
    await db.flush()


# ============== Available Columns ==============

AVAILABLE_COLUMNS: dict[ExportDataType, list[ExportColumn]] = {
    ExportDataType.EXPENSES: [
        ExportColumn(name="id", label="ID", type="string"),
        ExportColumn(name="date", label="Date", type="date"),
        ExportColumn(name="amount", label="Amount", type="currency"),
        ExportColumn(name="currency", label="Currency", type="string"),
        ExportColumn(name="cloud_account_id", label="Cloud Account", type="string"),
        ExportColumn(name="resource_id", label="Resource", type="string"),
        ExportColumn(name="service", label="Service", type="string"),
        ExportColumn(name="region", label="Region", type="string"),
        ExportColumn(name="tags", label="Tags", type="string"),
    ],
    ExportDataType.RESOURCES: [
        ExportColumn(name="id", label="ID", type="string"),
        ExportColumn(name="name", label="Name", type="string"),
        ExportColumn(name="resource_type", label="Type", type="string"),
        ExportColumn(name="cloud_type", label="Cloud", type="string"),
        ExportColumn(name="cloud_account_id", label="Cloud Account", type="string"),
        ExportColumn(name="region", label="Region", type="string"),
        ExportColumn(name="status", label="Status", type="string"),
        ExportColumn(name="created_at", label="Created At", type="datetime"),
        ExportColumn(name="tags", label="Tags", type="string"),
    ],
    ExportDataType.RECOMMENDATIONS: [
        ExportColumn(name="id", label="ID", type="string"),
        ExportColumn(name="title", label="Title", type="string"),
        ExportColumn(name="description", label="Description", type="string"),
        ExportColumn(name="recommendation_type", label="Type", type="string"),
        ExportColumn(name="severity", label="Severity", type="string"),
        ExportColumn(name="status", label="Status", type="string"),
        ExportColumn(name="potential_savings", label="Potential Savings", type="currency"),
        ExportColumn(name="currency", label="Currency", type="string"),
        ExportColumn(name="created_at", label="Created At", type="datetime"),
    ],
}


async def get_available_columns(data_type: ExportDataType) -> list[ExportColumn]:
    """Get available columns for a data type."""
    return AVAILABLE_COLUMNS.get(data_type, [])
