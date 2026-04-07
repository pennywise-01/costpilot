"""Shared dependencies for verifying organization membership."""

import logging
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from app.organizations.models import Employee
from app.shared.exceptions import ForbiddenError

logger = logging.getLogger(__name__)


async def verify_org_membership(db: AsyncSession, user_id: str, org_id: str) -> None:
    """Raise ForbiddenError if user is not a member of the organization."""
    result = await db.execute(
        select(Employee).where(
            Employee.auth_user_id == user_id,
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise ForbiddenError("You are not a member of this organization")


async def get_current_org_member(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    """Resolve the current user's Employee record for the given org.

    Raises ForbiddenError if the user is not a member.
    Returns the Employee row, which includes the org-scoped role.
    """
    logger.info(f"[DEBUG] get_current_org_member called - org_id={org_id}, user_id={current_user.id}, email={current_user.email}")
    result = await db.execute(
        select(Employee).where(
            Employee.auth_user_id == current_user.id,
            Employee.organization_id == org_id,
            Employee.deleted_at.is_(None),
        )
    )
    employee = result.scalar_one_or_none()
    if employee is None:
        logger.warning(f"[DEBUG] No employee record found for user_id={current_user.id}, org_id={org_id}")
        raise ForbiddenError("You are not a member of this organization")
    logger.info(f"[DEBUG] Found employee record: id={employee.id}, role={employee.role}")
    return employee
