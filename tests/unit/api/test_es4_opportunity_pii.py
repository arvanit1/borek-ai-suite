"""ES-4 — per-opportunity PII redaction configuration."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _client() -> TestClient:
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def test_opportunity_create_persists_pii_redaction_enabled() -> None:
    client = _client()
    enabled = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme",
            "opportunity_name": "PII On",
            "department": "Finance",
            "pii_redaction_enabled": True,
        },
    )
    disabled = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Beta",
            "opportunity_name": "PII Off",
            "department": "Finance",
            "pii_redaction_enabled": False,
        },
    )
    assert enabled.status_code == 201
    assert disabled.status_code == 201
    assert enabled.json()["pii_redaction_enabled"] is True
    assert disabled.json()["pii_redaction_enabled"] is False


def test_opportunity_patch_does_not_change_sibling_pii_setting() -> None:
    client = _client()
    enabled = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme",
            "opportunity_name": "PII Stay On",
            "department": "Finance",
            "pii_redaction_enabled": True,
        },
    )
    disabled = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Beta",
            "opportunity_name": "PII Stay Off",
            "department": "Finance",
            "pii_redaction_enabled": False,
        },
    )
    renamed = client.patch(
        f"/opportunities/{enabled.json()['id']}",
        headers=_headers(),
        json={"opportunity_name": "PII Still On"},
    )
    sibling = client.get(
        f"/opportunities/{disabled.json()['id']}",
        headers=_headers(),
    )
    assert renamed.status_code == 200
    assert renamed.json()["pii_redaction_enabled"] is True
    assert sibling.json()["pii_redaction_enabled"] is False
    flipped = client.patch(
        f"/opportunities/{disabled.json()['id']}",
        headers=_headers(),
        json={"pii_redaction_enabled": True},
    )
    original = client.get(
        f"/opportunities/{enabled.json()['id']}",
        headers=_headers(),
    )
    assert flipped.status_code == 200
    assert flipped.json()["pii_redaction_enabled"] is True
    assert original.json()["pii_redaction_enabled"] is True


def test_stage_a_live_mode_respects_opportunity_pii_setting(monkeypatch: object) -> None:
    from app.services.data.memory_store import get_memory_store
    from app.services.stage_a_orchestration import generate_framework_from_transcripts

    store = get_memory_store()
    enabled_id = store.create_opportunity(
        user_id=USER_ID,
        client_name="Acme",
        opportunity_name="Enabled",
        department="Finance",
        language="en",
        pii_redaction_enabled=True,
    )["id"]
    disabled_id = store.create_opportunity(
        user_id=USER_ID,
        client_name="Beta",
        opportunity_name="Disabled",
        department="Finance",
        language="en",
        pii_redaction_enabled=False,
    )["id"]
    source = {
        "id": uuid.uuid4(),
        "file_name": "call.txt",
        "conversation_id": "C1",
        "sections": [
            {
                "section_index": 0,
                "speaker_role": "Alex",
                "content": "Email me at alex@example.com",
                "metadata": {"conversation_id": "C1"},
            }
        ],
    }
    for opportunity_id in (enabled_id, disabled_id):
        store.create_transcript(
            opportunity_id=opportunity_id,
            user_id=USER_ID,
            file_name="call.txt",
            mime_type="text/plain",
            storage_path=f"{opportunity_id}/call.txt",
            conversation_id="C1",
            content=b"Alex: Email me at alex@example.com",
            sections=source["sections"],
        )

    seen: list[bool] = []

    def extract(turns: list[Any], identity: Any, *, redact: bool) -> dict[str, Any]:
        seen.append(redact)
        return {"facts": [], "conversation_id": "C1"}

    monkeypatch.setattr(
        "app.services.stage_a_orchestration.settings.AI_EXECUTION_MODE",
        "live",
    )
    generate_framework_from_transcripts(
        store,
        opportunity_id=enabled_id,
        user_id=USER_ID,
        extract_fn=extract,
        generate_fn=lambda *args, **kwargs: {"title": "Enabled", "chapters": []},
    )
    generate_framework_from_transcripts(
        store,
        opportunity_id=disabled_id,
        user_id=USER_ID,
        extract_fn=extract,
        generate_fn=lambda *args, **kwargs: {"title": "Disabled", "chapters": []},
    )
    assert seen == [True, False]
