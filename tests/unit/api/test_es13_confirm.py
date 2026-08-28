"""ES-13 enforcement on the production MemoryDataStore confirm path."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.services.data.memory_store import MemoryDataStore, reset_memory_store
from app.services.framework_generation import confirm_framework


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
    chapter_6 = next(ch for ch in framework_json["chapters"] if ch["chapter_id"] == "6")
    ai_split = next(block for block in chapter_6["body"] if block.get("block") == "ai_split")
    ai_split["used_for"] = ["Deciding whether a case matches"]
    ai_split["not_used_for"] = ["Deciding whether a case matches"]
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
