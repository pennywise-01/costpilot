"""HTTP API for advisor findings."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.advisor_findings.schemas import AdvisorFindingResponse
from app.advisor_findings.service import (
    collect_advisor_findings_for_org,
    list_findings_for_org,
)
from app.database import get_db
from app.enterprise.modules.rbac.dependencies import require_org_permission
from app.organizations.models import Employee
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member

router = APIRouter()


@router.get(
    "/organizations/{org_id}/advisor-findings",
    response_model=list[AdvisorFindingResponse],
    dependencies=[
        Depends(require_org_permission(PermissionAction.READ, RBACResourceType.RECOMMENDATION))
    ],
)
async def list_advisor_findings_endpoint(
    org_id: str,
    builtin_rule_id: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """List the most recent advisor findings for an organization."""
    findings = await list_findings_for_org(
        db, org_id, builtin_rule_id=builtin_rule_id, limit=limit,
    )
    return [AdvisorFindingResponse.model_validate(f) for f in findings]


@router.post(
    "/organizations/{org_id}/advisor-findings/refresh",
    response_model=dict,
    dependencies=[
        Depends(require_org_permission(PermissionAction.UPDATE, RBACResourceType.RECOMMENDATION))
    ],
)
async def refresh_advisor_findings_endpoint(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an on-demand advisor scan for the org's eligible accounts."""
    count = await collect_advisor_findings_for_org(db, org_id)
    return {"persisted": count}
