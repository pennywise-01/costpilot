from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.organizations.models import Employee, Organization
from app.pools.models import Pool
from app.shared.enums import PoolPurpose, RolePurpose
from app.shared.exceptions import ConflictError, NotFoundError
from app.shared.utils.time import utc_now


async def create_organization(
    db: AsyncSession, user: User, name: str, currency: str = "USD"
) -> Organization:
    """Create a new organization with default RBAC roles and owner assignment."""
    from app.enterprise.modules.rbac.service import (
        seed_default_roles,
        get_default_owner_role,
        assign_role,
    )
    
    # Create organization
    org = Organization(name=name, currency=currency)
    db.add(org)
    await db.flush()

    # Create root pool
    root_pool = Pool(
        name=name,
        organization_id=org.id,
        limit=0,
        purpose=PoolPurpose.BUDGET,
    )
    db.add(root_pool)
    await db.flush()

    org.pool_id = root_pool.id

    # Create employee record
    employee = Employee(
        name=user.display_name,
        organization_id=org.id,
        auth_user_id=user.id,
        role=RolePurpose.MANAGER,
        joined_at=utc_now(),
    )
    db.add(employee)
    await db.flush()

    # Seed default RBAC roles
    await seed_default_roles(db, org.id)
    
    # Assign owner role to creator
    owner_role = await get_default_owner_role(db, org.id)
    if owner_role:
        await assign_role(
            db, org.id, user.id, owner_role.id,
            assigned_by=user.id
        )

    # Seed default dashboard inside the org creation transaction
    from app.dashboards.seed import seed_default_dashboard
    await seed_default_dashboard(db, org.id, user.id)

    await db.commit()
    await db.refresh(org)

    return org


async def list_organizations(db: AsyncSession, user_id: str) -> list[Organization]:
    result = await db.execute(
        select(Organization)
        .join(Employee, Employee.organization_id == Organization.id)
        .where(
            Employee.auth_user_id == user_id,
            Employee.deleted_at.is_(None),
            Organization.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def list_organizations_with_roles(
    db: AsyncSession, user_id: str
) -> list[tuple[Organization, RolePurpose]]:
    result = await db.execute(
        select(Organization, Employee.role)
        .join(Employee, Employee.organization_id == Organization.id)
        .where(
            Employee.auth_user_id == user_id,
            Employee.deleted_at.is_(None),
            Organization.deleted_at.is_(None),
        )
    )
    return list(result.all())


async def get_organization(db: AsyncSession, org_id: str) -> Organization:
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id, Organization.deleted_at.is_(None)
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization not found")
    return org


async def update_organization(
    db: AsyncSession, org_id: str, data: dict
) -> Organization:
    org = await get_organization(db, org_id)

    for field, value in data.items():
        if value is not None:
            setattr(org, field, value)

    await db.flush()
    return org


async def delete_organization(db: AsyncSession, org_id: str) -> None:
    org = await get_organization(db, org_id)
    org.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def list_employees(db: AsyncSession, org_id: str, offset: int = 0, limit: int = 50) -> tuple[list[Employee], int]:
    await get_organization(db, org_id)

    # Get total count
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count(Employee.id)).where(
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Employee)
        .where(
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
        )
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def invite_employee(
    db: AsyncSession, org_id: str, email: str, name: str | None = None
) -> Employee:
    await get_organization(db, org_id)

    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None)).limit(1)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User with this email not found")

    result = await db.execute(
        select(Employee).where(
            Employee.organization_id == org_id,
            Employee.auth_user_id == user.id,
            Employee.deleted_at.is_(None),
        ).limit(1)
    )
    if result.scalar_one_or_none():
        raise ConflictError("User is already an employee of this organization")

    employee = Employee(
        name=name or user.display_name,
        organization_id=org_id,
        auth_user_id=user.id,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)

    return employee
