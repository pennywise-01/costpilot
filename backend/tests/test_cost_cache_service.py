"""Unit tests for cost cache service regression scenarios."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.cost_cache.schemas import CacheRefreshResult
from app.cost_cache.service import _update_cache_status, get_cached_summary


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_cached_summary_schedules_background_refresh_on_cache_miss() -> None:
    """Cache misses should schedule a background refresh without reusing request DB sessions."""
    db = AsyncMock()
    query_result = Mock()
    query_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=query_result)

    with patch("app.cost_cache.service._schedule_background_refresh") as mock_schedule:
        response = await get_cached_summary(db, "org-123", allow_stale=True)

    mock_schedule.assert_called_once_with("org-123")
    assert response.data_source == "uninitialized"
    assert response.this_month_total == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_cache_status_reads_refresh_result_fields() -> None:
    """Status updates should use CacheRefreshResult fields, not SQLAlchemy query result objects."""
    status = SimpleNamespace(
        last_successful_collection=None,
        last_collection_status=None,
        last_error_message=None,
        accounts_total=0,
        accounts_success=0,
        accounts_failed=0,
        next_collection_at=None,
    )

    query_result = Mock()
    query_result.scalar_one_or_none.return_value = status

    db = AsyncMock()
    db.execute = AsyncMock(return_value=query_result)
    db.flush = AsyncMock()
    db.add = Mock()

    refresh_result = CacheRefreshResult(
        success=True,
        accounts_total=3,
        accounts_success=3,
        accounts_failed=0,
    )

    await _update_cache_status(db, "org-123", refresh_result)

    assert status.last_collection_status == "success"
    assert status.last_successful_collection is not None
    assert isinstance(status.last_successful_collection, datetime)
    assert status.accounts_total == 3
    assert status.accounts_success == 3
    assert status.accounts_failed == 0
    assert status.next_collection_at is not None
