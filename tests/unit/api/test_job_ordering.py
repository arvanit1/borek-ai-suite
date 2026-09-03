"""Deterministic generation-job ordering across memory and Supabase stores."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.services.data.memory_store import MemoryDataStore
from app.services.data.supabase_store import SupabaseDataStore
from app.services.job_service import select_reconnect_job

OPPORTUNITY_ID = UUID("10000000-0000-4000-8000-000000000001")
LOWER_ID = UUID("20000000-0000-4000-8000-000000000001")
HIGHER_ID = UUID("20000000-0000-4000-8000-000000000002")
BASE_TIME = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _job_row(
    job_id: UUID,
    *,
    created_at: datetime = BASE_TIME,
    status: str = "QUEUED",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": job_id,
        "opportunity_id": OPPORTUNITY_ID,
        "presentation_id": None,
        "job_type": "presentation_generation",
        "status": status,
        "current_stage": status,
        "created_at": created_at,
        "started_at": started_at,
        "completed_at": completed_at,
    }


def test_memory_latest_job_prefers_newer_created_at() -> None:
    store = MemoryDataStore()
    store.create_generation_job(_job_row(HIGHER_ID, created_at=BASE_TIME))
    store.create_generation_job(
        _job_row(LOWER_ID, created_at=BASE_TIME + timedelta(seconds=1))
    )

    latest = store.get_latest_generation_job_for_opportunity(OPPORTUNITY_ID)

    assert latest is not None
    assert latest["id"] == LOWER_ID


def test_memory_latest_job_uses_descending_id_when_created_at_ties() -> None:
    store = MemoryDataStore()
    store.create_generation_job(_job_row(HIGHER_ID))
    store.create_generation_job(_job_row(LOWER_ID))

    latest = store.get_latest_generation_job_for_opportunity(OPPORTUNITY_ID)

    assert latest is not None
    assert latest["id"] == HIGHER_ID


def test_supabase_latest_job_requests_timestamp_and_id_descending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SupabaseDataStore("test-access-token")
    captured_params: dict[str, str] = {}

    def fake_request(
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> MagicMock:
        _ = json_body
        assert method == "GET"
        assert table == "generation_jobs"
        captured_params.update(params or {})
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [
            {
                **_job_row(HIGHER_ID),
                "id": str(HIGHER_ID),
                "opportunity_id": str(OPPORTUNITY_ID),
                "created_at": BASE_TIME.isoformat(),
            }
        ]
        return response

    monkeypatch.setattr(store, "_request", fake_request)

    latest = store.get_latest_generation_job_for_opportunity(OPPORTUNITY_ID)

    assert latest is not None
    assert latest["id"] == HIGHER_ID
    assert captured_params["order"] == "created_at.desc,id.desc"
    assert captured_params["limit"] == "1"


@pytest.mark.parametrize(
    ("status", "effective_field"),
    [("RUNNING", "started_at"), ("COMPLETED", "completed_at")],
)
def test_reconnect_uses_descending_id_when_effective_timestamps_tie(
    status: str,
    effective_field: str,
) -> None:
    lower = _job_row(LOWER_ID, status=status)
    higher = _job_row(HIGHER_ID, status=status)
    lower[effective_field] = BASE_TIME
    higher[effective_field] = BASE_TIME

    selected = select_reconnect_job([higher, lower], stage_group="presentation")

    assert selected is not None
    assert selected["id"] == HIGHER_ID
