from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.organizations.models import Employee
from app.pools.schemas import (
    PoolCreate,
    PoolUpdate,
    PoolResponse,
    PoolPolicyCreate,
    PoolPolicyResponse,
)
from app.pools.service import (
    create_pool,
    get_pool_tree,
    get_pool,
    update_pool,
    delete_pool,
    list_pool_policies,
    create_pool_policy,
    get_pool_tree_with_spent,
    enrich_pool_with_spent_and_owner,
)
from app.organizations.models import Employee
from sqlalchemy import select
from app.enterprise.modules.rbac.dependencies import ensure_org_permission, require_org_permission
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.org_access import get_current_org_member, verify_org_membership

router = APIRouter()


@router.post(
    "/organizations/{org_id}/pools",
    response_model=PoolResponse,
    status_code=201,
    dependencies=[Depends(require_org_permission(PermissionAction.CREATE, RBACResourceType.POOL))],
)
async def create(
    org_id: str,
    data: PoolCreate,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    pool = await create_pool(db, org_id, data)
    # Pre-fetch employees to avoid N+1 query
    emp_result = await db.execute(
        select(Employee).where(Employee.organization_id == org_id)
    )
    employees = {e.id: e.name for e in emp_result.scalars().all()}
    return await enrich_pool_with_spent_and_owner(db, pool, employees=employees)


@router.get(
    "/organizations/{org_id}/pools",
    response_model=list[PoolResponse],
    dependencies=[Depends(require_org_permission(PermissionAction.READ, RBACResourceType.POOL))],
)
async def list_all(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    pools = await get_pool_tree_with_spent(db, org_id)
    return pools


@router.get(
    "/pools/{id}",
    response_model=PoolResponse,
)
async def get_one(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pool = await get_pool(db, id)
    await verify_org_membership(db, current_user.id, pool.organization_id)
    await ensure_org_permission(
        db,
        pool.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.POOL,
    )
    return PoolResponse.model_validate(pool)


@router.patch(
    "/pools/{id}",
    response_model=PoolResponse,
)
async def update(
    id: str,
    data: PoolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pool = await get_pool(db, id)
    await verify_org_membership(db, current_user.id, pool.organization_id)
    await ensure_org_permission(
        db,
        pool.organization_id,
        current_user.id,
        PermissionAction.UPDATE,
        RBACResourceType.POOL,
    )
    pool = await update_pool(db, id, data)
    return PoolResponse.model_validate(pool)


@router.delete("/pools/{id}", status_code=204)
async def delete(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pool = await get_pool(db, id)
    await verify_org_membership(db, current_user.id, pool.organization_id)
    await ensure_org_permission(
        db,
        pool.organization_id,
        current_user.id,
        PermissionAction.DELETE,
        RBACResourceType.POOL,
    )
    await delete_pool(db, id)


@router.get(
    "/pools/{id}/policies",
    response_model=list[PoolPolicyResponse],
)
async def get_policies(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pool = await get_pool(db, id)
    await verify_org_membership(db, current_user.id, pool.organization_id)
    await ensure_org_permission(
        db,
        pool.organization_id,
        current_user.id,
        PermissionAction.READ,
        RBACResourceType.POOL,
    )
    policies = await list_pool_policies(db, id)
    return [PoolPolicyResponse.model_validate(p) for p in policies]


@router.post(
    "/pools/{id}/policies",
    response_model=PoolPolicyResponse,
    status_code=201,
)
async def create_policy(
    id: str,
    data: PoolPolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pool = await get_pool(db, id)
    await verify_org_membership(db, current_user.id, pool.organization_id)
    await ensure_org_permission(
        db,
        pool.organization_id,
        current_user.id,
        PermissionAction.MANAGE,
        RBACResourceType.POOL,
    )
    policy = await create_pool_policy(db, id, data)
    return PoolPolicyResponse.model_validate(policy)
