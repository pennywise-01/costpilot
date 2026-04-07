from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.organizations.models import Employee
from app.enterprise.modules.rbac.dependencies import ensure_org_permission, require_org_permission
from app.rules.schemas import RuleCreate, RuleUpdate, RuleResponse, PaginatedRules
from app.rules.service import create_rule, list_rules, get_rule, update_rule, delete_rule
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member, verify_org_membership
from app.shared.pagination import PaginatedResponse

router = APIRouter()


@router.post(
    "/organizations/{org_id}/rules",
    response_model=RuleResponse,
    status_code=201,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.RULE))],
)
async def create_rule_endpoint(
    org_id: str,
    data: RuleCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    # SEC-20: owner_id and creator_id set server-side from authenticated employee
    rule = await create_rule(db, org_id, member.id, member.id, data)
    return RuleResponse.model_validate(rule)


@router.get(
    "/organizations/{org_id}/rules",
    response_model=PaginatedRules,
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.RULE))],
)
async def list_rules_endpoint(
    org_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    rules, total = await list_rules(db, org_id, offset=offset, limit=page_size)
    return PaginatedResponse.create(
        items=[RuleResponse.model_validate(r) for r in rules],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule_endpoint(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rule(db, rule_id)
    await verify_org_membership(db, current_user.id, rule.organization_id)
    await ensure_org_permission(
        db,
        rule.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.RULE,
    )
    return RuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule_endpoint(
    rule_id: str,
    data: RuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rule(db, rule_id)
    await verify_org_membership(db, current_user.id, rule.organization_id)
    await ensure_org_permission(
        db,
        rule.organization_id,
        current_user.id,
        PermissionAction.UPDATE,
        RBACResourceType.RULE,
    )
    rule = await update_rule(db, rule_id, data)
    return RuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", response_model=RuleResponse)
async def delete_rule_endpoint(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rule(db, rule_id)
    await verify_org_membership(db, current_user.id, rule.organization_id)
    await ensure_org_permission(
        db,
        rule.organization_id,
        current_user.id,
        PermissionAction.DELETE,
        RBACResourceType.RULE,
    )
    rule = await delete_rule(db, rule_id)
    return RuleResponse.model_validate(rule)
