"""Stage 1 FE-01: Supabase regeneration appends a pinned Framework version."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from app.services.data.supabase_store import SupabaseDataStore
from app.services.framework_versioning import framework_source_revision

OPPORTUNITY_ID = UUID("11111111-1111-4111-8111-111111111111")
USER_ID = UUID("22222222-2222-4222-8222-222222222222")
SOURCE_ID = UUID("33333333-3333-4333-8333-333333333333")
DESTINATION_ID = UUID("44444444-4444-4444-8444-444444444444")


def test_supabase_regeneration_posts_new_version_without_patching(monkeypatch) -> None:
    store = SupabaseDataStore("test-token")
    source = {
        "id": SOURCE_ID,
        "opportunity_id": OPPORTUNITY_ID,
        "version_number": 4,
        "status": "draft",
        "framework_json": {"updated_at": "2026-09-16T00:00:00Z"},
    }
    monkeypatch.setattr(store, "get_framework_version", lambda **_kwargs: source)
    monkeypatch.setattr(store, "get_latest_framework", lambda **_kwargs: source)
    calls: list[tuple[str, str, dict]] = []

    def request(method: str, resource: str, **kwargs):
        payload = kwargs["json_body"]
        calls.append((method, resource, payload))
        row = {
            "id": str(DESTINATION_ID),
            "opportunity_id": str(OPPORTUNITY_ID),
            "version_number": 5,
            "status": "draft",
            "framework_json": payload["p_successor_json"],
            "created_by": str(USER_ID),
            "created_at": datetime(2026, 9, 16, tzinfo=UTC).isoformat(),
        }
        return SimpleNamespace(status_code=201, json=lambda: [row])

    monkeypatch.setattr(store, "_service_role_request", request)
    framework_json = {
        "version": 5,
        "previous_version_id": str(SOURCE_ID),
    }

    created = store.append_framework_version_transition(
        opportunity_id=OPPORTUNITY_ID,
        user_id=USER_ID,
        source_framework_version_id=SOURCE_ID,
        framework_version_id=DESTINATION_ID,
        framework_json=framework_json,
        status="draft",
        source_revision=framework_source_revision(source),
        transition="regenerate",
    )

    assert calls[0][0:2] == ("POST", "rpc/append_framework_version_transition")
    assert calls[0][2]["p_framework_version_id"] == str(DESTINATION_ID)
    assert calls[0][2]["p_source_framework_version_id"] == str(SOURCE_ID)
    assert calls[0][2]["p_successor_json"] == framework_json
    assert calls[0][2]["p_expected_source_json"] == source["framework_json"]
    assert created["id"] == DESTINATION_ID
