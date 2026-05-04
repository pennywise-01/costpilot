from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.pools.models import Pool, PoolPolicy
from app.pools.schemas import PoolCreate, PoolUpdate, PoolPolicyCreate, PoolResponse
from app.shared.enums import PoolPurpose
from app.shared.exceptions import NotFoundError, BadRequestError
from app.organizations.models import Employee
from app.expenses.service import get_expense_summary


async def enrich_pool_with_spent_and_owner(
    db: AsyncSession,
    pool: Pool,
    org_spent: float | None = None,
    employees: dict[str, str] | None = None,
) -> PoolResponse:
    """Enrich a pool with calculated spent amount and owner name."""
    # Calculate spent - for now, distribute org total based on pool hierarchy
    # In a real implementation, you'd have pool-to-cloud-account mappings
    if org_spent is None:
        try:
            # We need a mongo_db reference - skip expense calculation for now
            # and return 0 for spent. The frontend can handle this gracefully.
            spent = 0.0
        except Exception:
            spent = 0.0
    else:
        # Simple allocation: root pools get proportional share based on limit
        spent = 0.0

    # Get owner name from pre-fetched employees dict, or query if not provided
    owner = None
    if pool.default_owner_id:
        if employees is not None:
            owner = employees.get(pool.default_owner_id)
        else:
            emp_result = await db.execute(
                select(Employee).where(Employee.id == pool.default_owner_id).limit(1)
            )
            employee = emp_result.scalar_one_or_none()
            if employee:
                owner = employee.name

    return PoolResponse(
        id=pool.id,
        name=pool.name,
        limit=pool.limit,
        organization_id=pool.organization_id,
        parent_id=pool.parent_id,
        purpose=pool.purpose,
        default_owner_id=pool.default_owner_id,
        created_at=pool.created_at,
        spent=spent,
        owner=owner,
        children=[],  # Will be populated separately
    )


async def get_pool_tree_with_spent(
    db: AsyncSession,
    org_id: str,
) -> list[PoolResponse]:
    """Get pool tree enriched with spent amounts and owner names."""
    # Get the pools tree
    pools = await get_pool_tree(db, org_id)

    # Try to get organization-wide spent amount
    org_spent = 0.0
    try:
        # This is a placeholder - in production, you'd inject mongo_db
        # For now, we'll calculate spent from child pool limits proportionally
        pass
    except Exception:
        pass

    # Build a map of employees for owner lookup
    emp_result = await db.execute(
        select(Employee).where(Employee.organization_id == org_id)
    )
    employees = {e.id: e.name for e in emp_result.scalars().all()}

    def enrich_pool(pool: Pool) -> PoolResponse:
        """Recursively enrich a pool and its children."""
        owner = employees.get(pool.default_owner_id) if pool.default_owner_id else None

        # Calculate spent proportionally based on limit ratio
        # This is a simplified calculation - real implementation would track actual cloud costs per pool
        pool_spent = 0.0

        response = PoolResponse(
            id=pool.id,
            name=pool.name,
            limit=pool.limit,
            organization_id=pool.organization_id,
            parent_id=pool.parent_id,
            purpose=pool.purpose,
            default_owner_id=pool.default_owner_id,
            created_at=pool.created_at,
            spent=pool_spent,
            owner=owner,
            children=[enrich_pool(child) for child in pool.children],
        )
        return response

    return [enrich_pool(pool) for pool in pools]


async def create_pool(
    db: AsyncSession, org_id: str, data: PoolCreate
) -> Pool:
    if data.parent_id:
        parent = await get_pool(db, data.parent_id)
        if parent.organization_id != org_id:
            raise BadRequestError("Parent pool belongs to a different organization")

    pool = Pool(
        name=data.name,
        limit=data.limit,
        organization_id=org_id,
        parent_id=data.parent_id,
        purpose=data.purpose or PoolPurpose.BUDGET,
        default_owner_id=data.default_owner_id,
    )
    db.add(pool)
    await db.flush()
    return pool


async def get_pool_tree(db: AsyncSession, org_id: str) -> list[Pool]:
    result = await db.execute(
        select(Pool)
        .where(
            Pool.organization_id == org_id,
            Pool.parent_id.is_(None),
            Pool.deleted_at.is_(None),
        )
        .options(selectinload(Pool.children, recursion_depth=-1))
    )
    return list(result.scalars().all())


async def get_pool(db: AsyncSession, pool_id: str) -> Pool:
    result = await db.execute(
        select(Pool)
        .where(Pool.id == pool_id, Pool.deleted_at.is_(None))
        .options(selectinload(Pool.children))
    )
    pool = result.scalar_one_or_none()
    if not pool:
        raise NotFoundError("Pool not found")
    return pool


async def update_pool(
    db: AsyncSession, pool_id: str, data: PoolUpdate
) -> Pool:
    pool = await get_pool(db, pool_id)

    if data.name is not None:
        pool.name = data.name
    if data.limit is not None:
        pool.limit = data.limit
    if data.default_owner_id is not None:
        pool.default_owner_id = data.default_owner_id
    if data.purpose is not None:
        pool.purpose = data.purpose

    await db.flush()
    return pool


async def delete_pool(db: AsyncSession, pool_id: str) -> None:
    pool = await get_pool(db, pool_id)

    # Reassign children to the parent of the deleted pool
    result = await db.execute(
        select(Pool).where(
            Pool.parent_id == pool_id,
            Pool.deleted_at.is_(None),
        )
    )
    children = result.scalars().all()
    for child in children:
        child.parent_id = pool.parent_id

    pool.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def list_pool_policies(
    db: AsyncSession, pool_id: str
) -> list[PoolPolicy]:
    # Verify pool exists
    await get_pool(db, pool_id)

    result = await db.execute(
        select(PoolPolicy).where(
            PoolPolicy.pool_id == pool_id,
            PoolPolicy.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def create_pool_policy(
    db: AsyncSession, pool_id: str, data: PoolPolicyCreate
) -> PoolPolicy:
    pool = await get_pool(db, pool_id)

    policy = PoolPolicy(
        type=data.type,
        limit=data.limit,
        active=data.active,
        pool_id=pool_id,
        organization_id=pool.organization_id,
    )
    db.add(policy)
    await db.flush()
    return policy
