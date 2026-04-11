"""API router for Data Export endpoints."""

import hmac
import hashlib
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.enterprise.modules.rbac.dependencies import ensure_org_permission, require_org_permission
from app.enterprise.modules.export.enums import ExportDataType, ExportFormat, ExportStatus
from app.enterprise.modules.export.schemas import (
    AvailableColumnsResponse,
    DeliveryConfig,
    EmailDeliveryConfig,
    ExportDownloadResponse,
    ExportJobCreate,
    ExportJobListResponse,
    ExportJobResponse,
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportTemplateCreate,
    ExportTemplateResponse,
    ExportTemplateUpdate,
    ScheduledExportCreate,
    ScheduledExportResponse,
    ScheduledExportUpdate,
)
from app.enterprise.modules.export.service import (
    create_export_job,
    create_export_template,
    create_scheduled_export,
    delete_export_template,
    delete_scheduled_export,
    execute_export_job,
    get_available_columns,
    get_export_storage_dir,
    get_export_job,
    get_export_template,
    is_export_file_path_allowed,
    list_export_jobs,
    list_export_templates,
    list_scheduled_exports,
    stream_csv_data,
    stream_json_data,
    update_export_template,
    update_scheduled_export,
)
from app.organizations.models import Employee
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member
from app.shared.utils.time import utc_now

router = APIRouter(tags=["Data Export"])


# ============== Signed Export Download Tokens ==============

EXPORT_TOKEN_MAX_AGE_SECONDS = 900  # 15 minutes


def generate_export_token(job_id: str, org_id: str) -> str:
    """Generate time-limited HMAC token for export download."""
    timestamp = str(int(time.time()))
    message = f"{job_id}:{org_id}:{timestamp}"
    signature = hmac.new(
        settings.JWT_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{signature}:{timestamp}"


def verify_export_token(token: str, job_id: str, org_id: str, max_age: int = EXPORT_TOKEN_MAX_AGE_SECONDS) -> bool:
    """Verify an export download token."""
    try:
        signature, timestamp = token.rsplit(":", 1)
        timestamp = int(timestamp)
        if int(time.time()) - timestamp > max_age:
            return False
        message = f"{job_id}:{org_id}:{timestamp}"
        expected = hmac.new(
            settings.JWT_SECRET.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


# ============== Export Templates ==============

@router.post(
    "/organizations/{org_id}/export-templates",
    response_model=ExportTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.ENTERPRISE))],
)
async def create_template(
    org_id: str,
    data: ExportTemplateCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a new export template."""
    template = await create_export_template(db, org_id, member.auth_user_id, data)
    return ExportTemplateResponse.model_validate(template)


@router.get(
    "/organizations/{org_id}/export-templates",
    response_model=list[ExportTemplateResponse],
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def list_templates(
    org_id: str,
    data_type: ExportDataType | None = Query(None),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List export templates for an organization."""
    templates = await list_export_templates(db, org_id, data_type)
    return [ExportTemplateResponse.model_validate(t) for t in templates]


@router.get(
    "/organizations/{org_id}/export-templates/{template_id}",
    response_model=ExportTemplateResponse,
)
async def get_template(
    org_id: str,
    template_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get an export template by ID."""
    template = await get_export_template(db, org_id, template_id)
    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.READ,
        RBACResourceType.ENTERPRISE,
    )
    return ExportTemplateResponse.model_validate(template)


@router.patch(
    "/organizations/{org_id}/export-templates/{template_id}",
    response_model=ExportTemplateResponse,
)
async def update_template(
    org_id: str,
    template_id: str,
    data: ExportTemplateUpdate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Update an export template."""
    await get_export_template(db, org_id, template_id)
    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.UPDATE,
        RBACResourceType.ENTERPRISE,
    )
    template = await update_export_template(db, org_id, template_id, data)
    return ExportTemplateResponse.model_validate(template)


@router.delete(
    "/organizations/{org_id}/export-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template(
    org_id: str,
    template_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Delete an export template."""
    await get_export_template(db, org_id, template_id)
    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.DELETE,
        RBACResourceType.ENTERPRISE,
    )
    await delete_export_template(db, org_id, template_id)
    return None


# ============== Export Jobs ==============

@router.post(
    "/organizations/{org_id}/exports",
    response_model=ExportJobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.ENTERPRISE))],
)
async def create_export(
    org_id: str,
    data: ExportJobCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Create and queue a new export job."""
    job = await create_export_job(db, org_id, member.auth_user_id, data)
    # Generate a signed download token for the created export job
    download_token = generate_export_token(job.id, org_id)
    response = ExportJobResponse.model_validate(job)
    response.download_token = download_token
    return response


@router.get(
    "/organizations/{org_id}/exports",
    response_model=ExportJobListResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def list_exports(
    org_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: ExportStatus | None = Query(None),
    data_type: ExportDataType | None = Query(None),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List export jobs for an organization."""
    result = await list_export_jobs(db, org_id, page, limit, status, data_type)
    return ExportJobListResponse(
        items=[ExportJobResponse.model_validate(j) for j in result["items"]],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        pages=result["pages"],
    )


@router.get(
    "/organizations/{org_id}/exports/{job_id}",
    response_model=ExportJobResponse,
)
async def get_export(
    org_id: str,
    job_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get an export job by ID."""
    job = await get_export_job(db, org_id, job_id)
    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.READ,
        RBACResourceType.ENTERPRISE,
    )
    return ExportJobResponse.model_validate(job)


@router.post(
    "/organizations/{org_id}/exports/{job_id}/execute",
    response_model=ExportJobResponse,
)
async def execute_export(
    org_id: str,
    job_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Execute a pending export job."""
    await get_export_job(db, org_id, job_id)
    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.MANAGE,
        RBACResourceType.ENTERPRISE,
    )
    job = await execute_export_job(db, org_id, job_id)
    return ExportJobResponse.model_validate(job)


@router.get(
    "/organizations/{org_id}/exports/{job_id}/download",
    response_model=ExportDownloadResponse,
)
async def download_export(
    org_id: str,
    job_id: str,
    request: Request,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Get download URL for a completed export."""
    job = await get_export_job(db, org_id, job_id)
    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.READ,
        RBACResourceType.ENTERPRISE,
    )
    
    if job.status != ExportStatus.COMPLETED:
        from app.shared.exceptions import BadRequestError
        raise BadRequestError("Export is not ready for download")

    if job.expires_at and job.expires_at.replace(tzinfo=None) < utc_now().replace(tzinfo=None):
        from app.shared.exceptions import BadRequestError
        raise BadRequestError("Export has expired")
    
    # Generate temporary download URL with signed token (SEC-14)
    base_url = str(request.base_url).rstrip("/")
    download_token = generate_export_token(job_id, org_id)
    download_url = f"{base_url}/api/v1/enterprise/organizations/{org_id}/exports/{job_id}/file?download_token={download_token}"

    return ExportDownloadResponse(
        download_url=download_url,
        expires_in_seconds=EXPORT_TOKEN_MAX_AGE_SECONDS,
        filename=f"export_{job_id}.{job.format}",
        file_size_bytes=job.file_size_bytes,
        download_token=download_token,
    )


@router.get(
    "/organizations/{org_id}/exports/{job_id}/file",
)
async def get_export_file(
    org_id: str,
    job_id: str,
    download_token: str | None = Query(None, description="Signed download token (SEC-14)"),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Download the export file directly."""
    from fastapi.responses import FileResponse

    # SEC-14: Validate signed download token if provided
    if download_token and not verify_export_token(download_token, job_id, org_id):
        from app.shared.exceptions import ForbiddenError
        raise ForbiddenError("Expired or invalid download token")

    job = await get_export_job(db, org_id, job_id)
    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.READ,
        RBACResourceType.ENTERPRISE,
    )

    if job.status != ExportStatus.COMPLETED or not job.file_path:
        from app.shared.exceptions import BadRequestError
        raise BadRequestError("Export file not available")

    if not is_export_file_path_allowed(job.file_path):
        from app.shared.exceptions import BadRequestError
        raise BadRequestError("Invalid export file path")

    import os
    safe_filename = os.path.basename(job.file_path)
    if not safe_filename:
        from app.shared.exceptions import BadRequestError
        raise BadRequestError("Invalid export file path")

    safe_file_path = get_export_storage_dir() / safe_filename
    if not safe_file_path.exists():
        from app.shared.exceptions import NotFoundError
        raise NotFoundError("Export file not found")

    try:
        resolved_safe_path = safe_file_path.resolve()
        resolved_safe_path.relative_to(get_export_storage_dir().resolve())
    except (OSError, RuntimeError, ValueError):
        from app.shared.exceptions import BadRequestError
        raise BadRequestError("Invalid export file path")

    # SEC-14: Audit the export download
    from app.security.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
    try:
        audit_logger = get_audit_logger()
        await audit_logger.log(
            db=db,
            event_type=AuditEventType.DATA_EXPORTED,
            severity=AuditSeverity.INFO,
            user_id=member.auth_user_id,
            org_id=org_id,
            resource_type="export",
            resource_id=job_id,
            action_details={
                "export_type": job.data_type.value if hasattr(job.data_type, "value") else str(job.data_type),
                "format": job.format.value if hasattr(job.format, "value") else str(job.format),
                "file_size_bytes": job.file_size_bytes,
                "download_method": "signed_token" if download_token else "authenticated",
            },
            success=True,
        )
    except Exception:
        pass  # Do not block download on audit failure

    media_types = {
        "csv": "text/csv",
        "json": "application/json",
        "parquet": "application/octet-stream",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }

    return FileResponse(
        path=str(resolved_safe_path),
        filename=f"export_{job.data_type}_{job_id}.{job.format}",
        media_type=media_types.get(job.format, "application/octet-stream"),
    )


@router.get(
    "/organizations/{org_id}/exports/stream",
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def stream_export(
    org_id: str,
    data_type: str = Query(..., description="expenses, resources, or recommendations"),
    format: str = Query("csv", description="csv or json"),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Stream export data as CSV or JSON without loading everything into memory."""
    from app.database import get_mongo_db
    from app.enterprise.modules.export.service import (
        fetch_expense_data,
        fetch_recommendation_data,
        fetch_resource_data,
    )

    await ensure_org_permission(
        db,
        org_id,
        member.auth_user_id,
        PermissionAction.READ,
        RBACResourceType.ENTERPRISE,
    )

    mongo_db = get_mongo_db()

    # Build query function based on data_type
    async def query_func(limit: int, offset: int):
        if data_type == "expenses":
            from app.expenses.service import get_clean_expenses

            expenses = await get_clean_expenses(mongo_db, org_id, limit=limit, offset=offset)
            return [
                {
                    "id": e.resource_id,
                    "date": None,
                    "amount": float(e.cost or 0),
                    "currency": "USD",
                    "cloud_account_id": e.cloud_account_id,
                    "resource_id": e.resource_id,
                    "service": e.resource_name,
                    "region": e.region,
                    "tags": {},
                }
                for e in expenses
            ]
        elif data_type == "resources":
            from app.resources.service import list_resources

            response = await list_resources(mongo_db, org_id, limit=limit, offset=offset)
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "resource_type": r.resource_type,
                    "cloud_type": r.cloud_type,
                    "cloud_account_id": r.cloud_account_id,
                    "region": r.region,
                    "status": "active" if r.active else "inactive",
                    "created_at": r.first_seen,
                    "tags": r.tags,
                }
                for r in response.resources
            ]
        elif data_type == "recommendations":
            from app.recommendations.service import get_recommendations_overview

            overview = await get_recommendations_overview(mongo_db, org_id, db=db)
            rows = []
            for rec in overview.recommendations:
                if rec.items:
                    for idx, item in enumerate(rec.items):
                        rows.append(
                            {
                                "id": item.get("id") or f"{rec.type}-{idx}",
                                "title": item.get("title") or item.get("name") or rec.name,
                                "description": item.get("description") or rec.description,
                                "recommendation_type": rec.type,
                                "severity": item.get("severity") or "medium",
                                "status": "dismissed" if item.get("dismissed") else "open",
                                "potential_savings": float(item.get("saving") or rec.saving),
                                "currency": item.get("currency") or "USD",
                                "created_at": item.get("created_at"),
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
            # Apply pagination manually since overview returns all
            return rows[offset : offset + limit]
        return []

    if format == "csv":
        return StreamingResponse(
            stream_csv_data(query_func),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={data_type}_export.csv"},
        )
    else:
        return StreamingResponse(
            stream_json_data(query_func),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={data_type}_export.json"},
        )


# ============== Scheduled Exports ==============

@router.post(
    "/organizations/{org_id}/scheduled-exports",
    response_model=ScheduledExportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.ENTERPRISE))],
)
async def create_scheduled(
    org_id: str,
    data: ScheduledExportCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a new scheduled export."""
    scheduled = await create_scheduled_export(db, org_id, member.auth_user_id, data)
    return ScheduledExportResponse.model_validate(scheduled)


@router.get(
    "/organizations/{org_id}/scheduled-exports",
    response_model=list[ScheduledExportResponse],
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def list_scheduled(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List scheduled exports for an organization."""
    scheduled = await list_scheduled_exports(db, org_id)
    return [ScheduledExportResponse.model_validate(s) for s in scheduled]


@router.patch(
    "/organizations/{org_id}/scheduled-exports/{scheduled_id}",
    response_model=ScheduledExportResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.UPDATE, RBACResourceType.ENTERPRISE))],
)
async def update_scheduled(
    org_id: str,
    scheduled_id: str,
    data: ScheduledExportUpdate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Update a scheduled export."""
    scheduled = await update_scheduled_export(db, org_id, scheduled_id, data)
    return ScheduledExportResponse.model_validate(scheduled)


@router.delete(
    "/organizations/{org_id}/scheduled-exports/{scheduled_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_org_permission(PermissionAction.DELETE, RBACResourceType.ENTERPRISE))],
)
async def delete_scheduled(
    org_id: str,
    scheduled_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scheduled export."""
    await delete_scheduled_export(db, org_id, scheduled_id)
    return None


# ============== Utility Endpoints ==============

@router.get(
    "/organizations/{org_id}/export-columns/{data_type}",
    response_model=AvailableColumnsResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def get_columns(
    org_id: str,
    data_type: ExportDataType,
    member: Employee = Depends(get_current_org_member),
):
    """Get available columns for a data type."""
    columns = await get_available_columns(data_type)
    return AvailableColumnsResponse(
        data_type=data_type,
        columns=columns,
    )


@router.post(
    "/organizations/{org_id}/export-preview",
    response_model=ExportPreviewResponse,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.ENTERPRISE))],
)
async def preview_export(
    org_id: str,
    data: ExportPreviewRequest,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Preview export data (returns sample rows)."""
    # Fetch sample data
    from app.enterprise.modules.export.service import (
        fetch_expense_data,
        fetch_resource_data,
        fetch_recommendation_data,
    )
    
    if data.data_type == ExportDataType.EXPENSES:
        rows = await fetch_expense_data(db, org_id, data.filters, None, None, None, None)
    elif data.data_type == ExportDataType.RESOURCES:
        rows = await fetch_resource_data(db, org_id, data.filters, None, None, None, None)
    elif data.data_type == ExportDataType.RECOMMENDATIONS:
        rows = await fetch_recommendation_data(db, org_id, data.filters, None, None, None, None)
    else:
        rows = []
    
    # Select requested columns
    preview_rows = []
    for row in rows[:data.limit]:
        preview_row = {col: row.get(col) for col in data.columns if col in row}
        preview_rows.append(preview_row)
    
    return ExportPreviewResponse(
        columns=data.columns,
        rows=preview_rows,
        total_count=len(rows),
    )
