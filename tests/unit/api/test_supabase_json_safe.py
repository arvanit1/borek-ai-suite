"""AT-37 — Supabase JSON body sanitization."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from app.services.data.supabase_store import _json_safe_value


def test_json_safe_value_recurses_nested_uuid_and_datetime() -> None:
    job_id = uuid.uuid4()
    payload = {
        "id": job_id,
        "result_json": {
            "llm_calls": [
                {
                    "job_id": job_id,
                    "timestamp": datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
                }
            ],
            "_enqueue": {"user_id": uuid.uuid4()},
        },
        "started_at": datetime(2026, 9, 1, 11, 0, tzinfo=UTC),
    }
    safe = _json_safe_value(payload)
    json.dumps(safe)
    assert safe["id"] == str(job_id)
    assert safe["result_json"]["llm_calls"][0]["job_id"] == str(job_id)
    assert isinstance(safe["result_json"]["llm_calls"][0]["timestamp"], str)
    assert isinstance(safe["result_json"]["_enqueue"]["user_id"], str)
