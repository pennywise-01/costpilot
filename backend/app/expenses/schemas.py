from datetime import datetime
from pydantic import BaseModel

class ExpenseSummary(BaseModel):
    this_month_total: float = 0
    last_month_total: float = 0
    this_month_forecast: float = 0
    change_percent: float = 0

class DailyExpense(BaseModel):
    date: str
    cost: float

class BreakdownItem(BaseModel):
    id: str
    name: str
    type: str | None = None
    total: float
    previous_total: float = 0
    daily_breakdown: list[DailyExpense] = []

class PartialFailure(BaseModel):
    account_id: str
    account_name: str
    cloud_type: str
    error: str


class ExpenseBreakdown(BaseModel):
    total: float
    previous_total: float = 0
    start_date: str
    end_date: str
    breakdown: list[BreakdownItem] = []
    daily_totals: list[DailyExpense] = []
    partial_failures: list[PartialFailure] = []
    has_errors: bool = False

class CleanExpense(BaseModel):
    resource_id: str
    resource_name: str
    resource_type: str | None = None
    cloud_account_id: str | None = None
    cloud_account_name: str | None = None
    cloud_type: str | None = None
    region: str | None = None
    owner_name: str | None = None
    pool_name: str | None = None
    cost: float = 0
