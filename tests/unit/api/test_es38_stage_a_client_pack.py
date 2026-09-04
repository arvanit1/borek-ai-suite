"""ES-38 — Stage A reads additional_client_information from the opportunity."""

from __future__ import annotations

import uuid
from typing import Any

from app.services.data.memory_store import get_memory_store
from app.services.stage_a_orchestration import generate_framework_from_transcripts

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PACK = {
    "location_requirements": ["EU hosting"],
    "constraints": ["Go-live by Q4"],
    "contacts": [{"name": "Ada Lovelace", "role": "Sponsor"}],
    "priorities": ["Accuracy"],
    "notes": "Procurement review is pending.",
}


def _seed(*, pack: dict[str, Any] | None = None) -> uuid.UUID:
    store = get_memory_store()
    opportunity = store.create_opportunity(
        user_id=USER_ID,
        client_name="Acme",
        opportunity_name="Invoice match",
        department="Finance",
        language="en",
        additional_client_information=pack,
    )
    store.create_transcript(
        opportunity_id=opportunity["id"],
        user_id=USER_ID,
        file_name="call.txt",
        mime_type="text/plain",
        storage_path=f"{opportunity['id']}/call.txt",
        conversation_id="C1",
        content=b"Alex: We match invoices in the ERP.",
        sections=[
            {
                "section_index": 0,
                "speaker_role": "Alex",
                "content": "We match invoices in the ERP.",
                "metadata": {"conversation_id": "C1"},
            }
        ],
    )
    return opportunity["id"]


def test_fixture_mode_without_pack_does_not_apply_client_pack() -> None:
    opportunity_id = _seed(pack=None)
    store = get_memory_store()
    framework = generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=USER_ID,
        execution_mode="fixture",
    )
    assert framework["generation_meta"]["client_pack"]["applied"] is False
    assert framework["generation_meta"]["client_pack"]["payload"] is None


def test_fixture_mode_applies_opportunity_client_pack() -> None:
    opportunity_id = _seed(pack=PACK)
    store = get_memory_store()
    framework = generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=USER_ID,
        execution_mode="fixture",
    )
    meta = framework["generation_meta"]["client_pack"]
    assert meta["applied"] is True
    assert meta["payload"]["location_requirements"] == ["EU hosting"]
    assert any("Go-live by Q4" in item["description"] for item in framework["open_items"])


def test_live_mode_passes_client_pack_into_extract_and_generate(monkeypatch: object) -> None:
    opportunity_id = _seed(pack=PACK)
    store = get_memory_store()
    seen: dict[str, Any] = {}

    def extract(turns: list[Any], identity: Any, *, redact: bool, client_pack: dict[str, Any] | None = None) -> dict[str, Any]:
        seen["extract_pack"] = client_pack
        return {"facts": [], "conversation_id": "C1"}

    def generate(models: list[Any], **kwargs: Any) -> dict[str, Any]:
        seen["generate_pack"] = kwargs.get("client_pack")
        return {"title": "Live", "chapters": [], "open_items": [], "generation_meta": {}}

    monkeypatch.setattr(
        "app.services.stage_a_orchestration.settings.AI_EXECUTION_MODE",
        "live",
    )
    generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=USER_ID,
        extract_fn=extract,
        generate_fn=generate,
    )
    assert seen["extract_pack"]["constraints"] == ["Go-live by Q4"]
    assert seen["generate_pack"]["priorities"] == ["Accuracy"]
    assert "made_up_field" not in (seen["extract_pack"] or {})
