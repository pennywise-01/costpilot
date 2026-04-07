from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.organizations.models import Employee
from app.enterprise.modules.rbac.dependencies import ensure_org_permission, require_org_permission
from app.recommendation_rules.schemas import RecRuleCreate, RecRuleUpdate, RecRuleResponse
from app.recommendation_rules.service import (
    create_rec_rule,
    list_rec_rules,
    get_rec_rule,
    update_rec_rule,
    delete_rec_rule,
)
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member, verify_org_membership

router = APIRouter()


@router.post(
    "/organizations/{org_id}/recommendation-rules",
    response_model=RecRuleResponse,
    status_code=201,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.RULE))],
)
async def create_rec_rule_endpoint(
    org_id: str,
    data: RecRuleCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    rule = await create_rec_rule(db, org_id, member.auth_user_id, data)
    return RecRuleResponse.model_validate(rule)


@router.get(
    "/organizations/{org_id}/recommendation-rules",
    response_model=list[RecRuleResponse],
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.RULE))],
)
async def list_rec_rules_endpoint(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    rules = await list_rec_rules(db, org_id)
    return [RecRuleResponse.model_validate(r) for r in rules]


@router.get("/recommendation-rules/{rule_id}", response_model=RecRuleResponse)
async def get_rec_rule_endpoint(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rec_rule(db, rule_id)
    await verify_org_membership(db, current_user.id, rule.organization_id)
    await ensure_org_permission(
        db,
        rule.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.RULE,
    )
    return RecRuleResponse.model_validate(rule)


@router.patch("/recommendation-rules/{rule_id}", response_model=RecRuleResponse)
async def update_rec_rule_endpoint(
    rule_id: str,
    data: RecRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rec_rule(db, rule_id)
    await verify_org_membership(db, current_user.id, rule.organization_id)
    await ensure_org_permission(
        db,
        rule.organization_id,
        current_user.id,
        PermissionAction.UPDATE,
        RBACResourceType.RULE,
    )
    rule = await update_rec_rule(db, rule_id, data)
    return RecRuleResponse.model_validate(rule)


@router.delete("/recommendation-rules/{rule_id}", response_model=RecRuleResponse)
async def delete_rec_rule_endpoint(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rec_rule(db, rule_id)
    await verify_org_membership(db, current_user.id, rule.organization_id)
    await ensure_org_permission(
        db,
        rule.organization_id,
        current_user.id,
        PermissionAction.DELETE,
        RBACResourceType.RULE,
    )
    rule = await delete_rec_rule(db, rule_id)
    return RecRuleResponse.model_validate(rule)
