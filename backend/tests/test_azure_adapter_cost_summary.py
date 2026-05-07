import pytest

from app.cloud_accounts.adapters.azure import AzureAdapter
from app.shared.exceptions import BadRequestError


def _build_adapter() -> AzureAdapter:
    return AzureAdapter(
        {
            "tenant_id": "tenant",
            "client_id": "client",
            "client_secret": "secret",
            "subscription_id": "subscription",
        }
    )


@pytest.mark.asyncio
async def test_monthly_summary_single_call_success(monkeypatch):
    """Combined monthly call succeeds — costs split by date column."""
    adapter = _build_adapter()

    async def fake_get_cost_and_usage(start_date, end_date, granularity="Daily", group_by=None):
        return {
            "columns": ["Cost", "UsageDate"],
            "rows": [
                [50.0, "2026-04-15"],  # last month
                [30.0, "2026-05-03"],  # this month
            ],
            "cost_index": 0,
            "date_index": 1,
        }

    monkeypatch.setattr(adapter, "get_cost_and_usage", fake_get_cost_and_usage)

    summary = await adapter.get_monthly_cost_summary()

    assert summary["this_month"] == 30.0
    assert summary["last_month"] == 50.0
    assert summary["forecast"] >= 30.0


@pytest.mark.asyncio
async def test_monthly_summary_no_date_column_all_to_this_month(monkeypatch):
    """When date_index is None, all costs go to this_month."""
    adapter = _build_adapter()

    async def fake_get_cost_and_usage(start_date, end_date, granularity="Daily", group_by=None):
        return {
            "columns": ["Cost"],
            "rows": [[0.01]],
            "cost_index": 0,
            "date_index": None,
        }

    monkeypatch.setattr(adapter, "get_cost_and_usage", fake_get_cost_and_usage)

    summary = await adapter.get_monthly_cost_summary()

    assert summary["this_month"] == 0.01
    assert summary["last_month"] == 0.0
    assert summary["forecast"] >= 0.01


@pytest.mark.asyncio
async def test_monthly_summary_falls_back_to_daily_when_monthly_fails(monkeypatch):
    """Combined monthly fails → falls back to combined daily (2 calls total)."""
    adapter = _build_adapter()
    granularities = []

    async def fake_get_cost_and_usage(start_date, end_date, granularity="Daily", group_by=None):
        granularities.append(granularity)
        if granularity == "Monthly":
            raise BadRequestError("Azure Cost Management error: (429) Too many requests. Please retry.")
        return {
            "columns": ["Cost"],
            "rows": [[0.01], [0.02]],
            "cost_index": 0,
            "date_index": None,
        }

    monkeypatch.setattr(adapter, "get_cost_and_usage", fake_get_cost_and_usage)

    summary = await adapter.get_monthly_cost_summary()

    assert granularities == ["Monthly", "Daily"]
    assert summary["this_month"] == 0.03
    assert summary["last_month"] == 0.0
