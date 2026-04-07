from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.shared.pagination import PaginatedResponse


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    currency: str | None = Field(None, min_length=3, max_length=3)
    disabled: bool | None = None


class OrgResponse(BaseModel):
    id: str
    name: str
    currency: str
    pool_id: str | None
    is_demo: bool
    disabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgWithRoleResponse(BaseModel):
    id: str
    name: str
    currency: str
    pool_id: str | None
    is_demo: bool
    disabled: bool
    created_at: datetime
    role: str

    model_config = {"from_attributes": True}


class EmployeeResponse(BaseModel):
    id: str
    name: str
    organization_id: str
    auth_user_id: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeInvite(BaseModel):
    email: EmailStr
    name: str | None = Field(None, min_length=1, max_length=256)


class PaginatedEmployees(PaginatedResponse[EmployeeResponse]):
    """Paginated response for employees list."""
    pass
