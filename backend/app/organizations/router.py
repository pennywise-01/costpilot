from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.organizations.models import Employee
from app.organizations.schemas import (
    EmployeeInvite,
    EmployeeResponse,
    OrgCreate,
    OrgResponse,
    OrgUpdate,
    OrgWithRoleResponse,
    PaginatedEmployees,
)
from app.organizations.service import (
    create_organization,
    delete_organization,
    invite_employee,
    list_employees,
    list_organizations_with_roles,
    update_organization,
)
from app.enterprise.modules.rbac.schemas import PermissionCheckRequest
from app.enterprise.modules.rbac.service import check_permission
from app.shared.enums import PermissionAction, RBACResourceType
from app.shared.exceptions import ForbiddenError
from app.shared.org_access import get_current_org_member
from app.shared.pagination import PaginatedResponse

router = APIRouter()


async def _require_org_admin(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    result = await check_permission(
        db,
        org_id,
        PermissionCheckRequest(
            user_id=member.auth_user_id,
            action=PermissionAction.MANAGE,
            resource_type=RBACResourceType.ORGANIZATION,
        ),
    )
    if not result.allowed:
        raise ForbiddenError("You don't have permission to manage this organization")
    return member


async def _require_manage_users_in_org(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    result = await check_permission(
        db,
        org_id,
        PermissionCheckRequest(
            user_id=member.auth_user_id,
            action=PermissionAction.MANAGE,
            resource_type=RBACResourceType.USER,
        ),
    )
    if not result.allowed:
        raise ForbiddenError("You don't have permission to manage organization users")
    return member


@router.post("", response_model=OrgResponse)
async def create_org(
    data: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await create_organization(db, current_user, data.name, data.currency)
    return OrgResponse.model_validate(org)


@router.get("", response_model=list[OrgWithRoleResponse])
async def list_orgs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await list_organizations_with_roles(db, current_user.id)
    return [
        OrgWithRoleResponse(
            id=org.id,
            name=org.name,
            currency=org.currency,
            pool_id=org.pool_id,
            is_demo=org.is_demo,
            disabled=org.disabled,
            created_at=org.created_at,
            role=role.value if hasattr(role, "value") else role,
        )
        for org, role in rows
    ]


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: str,
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    from app.organizations.service import get_organization

    org = await get_organization(db, org_id)
    return OrgResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_org(
    org_id: str,
    data: OrgUpdate,
    member: Employee = Depends(_require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    org = await update_organization(db, org_id, data.model_dump(exclude_unset=True))
    return OrgResponse.model_validate(org)


@router.delete("/{org_id}", status_code=204)
async def delete_org(
    org_id: str,
    member: Employee = Depends(_require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    await delete_organization(db, org_id)


@router.get("/{org_id}/employees", response_model=PaginatedEmployees)
async def get_employees(
    org_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    member: Employee = Depends(get_current_org_member),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    employees, total = await list_employees(db, org_id, offset=offset, limit=page_size)
    return PaginatedResponse.create(
        items=[EmployeeResponse.model_validate(emp) for emp in employees],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{org_id}/employees/invite", response_model=EmployeeResponse)
async def invite_emp(
    org_id: str,
    data: EmployeeInvite,
    member: Employee = Depends(_require_manage_users_in_org),
    db: AsyncSession = Depends(get_db),
):
    employee = await invite_employee(db, org_id, data.email, data.name)
    return EmployeeResponse.model_validate(employee)
