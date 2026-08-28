"""ES-13 enforcement on production Memory and Supabase confirm paths."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.data.memory_store import MemoryDataStore, reset_memory_store
from app.services.data.supabase_store import SupabaseDataStore
from app.services.framework_generation import confirm_framework
from app.services.framework_stub_template import load_framework_stub_template


def _contradictory_chapter_6(framework_json: dict[str, Any]) -> None:
    chapter_6 = next(ch for ch in framework_json["chapters"] if ch["chapter_id"] == "6")
    ai_split = next(block for block in chapter_6["body"] if block.get("block") == "ai_split")
    ai_split["used_for"] = ["Deciding whether a case matches"]
    ai_split["not_used_for"] = ["Deciding whether a case matches"]


def test_memory_store_confirm_runs_es13_gate() -> None:
    reset_memory_store()
    store = MemoryDataStore()
    user_id = uuid.uuid4()
    opportunity = store.create_opportunity(
        user_id=user_id,
        client_name="Acme",
        opportunity_name="Invoice Automation",
        department="Finance",
        language="en",
    )
    opportunity_id = opportunity["id"]
    row = store.generate_framework_stub(opportunity_id=opportunity_id, user_id=user_id)
    framework_json = row["framework_json"]
    _contradictory_chapter_6(framework_json)
    store.update_latest_framework(
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_json=framework_json,
    )

    with pytest.raises(HTTPException) as exc_info:
        confirm_framework(
            store,
            opportunity_id=opportunity_id,
            user_id=user_id,
            framework_version_id=None,
        )

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "PRE_CONFIRM_FAILED"

    latest = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
    assert latest["status"] == "draft"


def test_supabase_store_confirm_runs_es13_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    store = SupabaseDataStore("test-access-token")
    user_id = uuid.uuid4()
    opportunity_id = uuid.uuid4()
    framework_version_id = uuid.uuid4()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    framework_json = load_framework_stub_template(opportunity_id)
    _contradictory_chapter_6(framework_json)

    opportunity_row = {
        "id": str(opportunity_id),
        "client_name": "Acme",
        "opportunity_name": "Invoice Automation",
        "department": "Finance",
        "language": "en",
        "status": "active",
        "created_by": str(user_id),
        "created_at": now,
        "updated_at": now,
    }
    framework_row = {
        "id": str(framework_version_id),
        "opportunity_id": str(opportunity_id),
        "version_number": 1,
        "status": "draft",
        "framework_json": framework_json,
        "created_by": str(user_id),
        "created_at": now,
    }
    confirm_patches: list[dict[str, Any]] = []

    def fake_request(
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> MagicMock:
        response = MagicMock()
        if method == "GET" and table == "opportunities":
            response.status_code = 200
            response.json.return_value = [opportunity_row]
            return response
        if method == "GET" and table == "framework_versions":
            response.status_code = 200
            response.json.return_value = [framework_row]
            return response
        if method == "PATCH" and table == "framework_versions":
            confirm_patches.append(json_body or {})
            response.status_code = 200
            confirmed = {
                **framework_row,
                "status": "confirmed",
                "framework_json": {**framework_json, "status": "confirmed"},
            }
            response.json.return_value = [confirmed]
            return response
        response.status_code = 404
        response.json.return_value = []
        response.text = "unexpected request"
        return response

    monkeypatch.setattr(store, "_request", fake_request)

    with pytest.raises(HTTPException) as exc_info:
        confirm_framework(
            store,
            opportunity_id=opportunity_id,
            user_id=user_id,
            framework_version_id=None,
        )

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "PRE_CONFIRM_FAILED"
    assert confirm_patches == []
    assert framework_row["status"] == "draft"
