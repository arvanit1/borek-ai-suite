"""ES-39 — Stage A retrieves company facts from the active corpus, never ingest."""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.services.data.memory_store import get_memory_store
from app.services.stage_a_orchestration import generate_framework_from_transcripts

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _seed(*, name: str) -> uuid.UUID:
    store = get_memory_store()
    opportunity = store.create_opportunity(
        user_id=USER_ID,
        client_name="Acme",
        opportunity_name=name,
        department="Finance",
        language="en",
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


def test_fixture_mode_cites_dummy_invoice_company_facts() -> None:
    opportunity_id = _seed(name="Invoice 3-Way Match")
    store = get_memory_store()
    framework = generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=USER_ID,
        execution_mode="fixture",
    )
    meta = framework["generation_meta"]["company_facts"]
    pricing = next(item for item in meta["lookups"] if item["kind"] == "pricing")
    assert meta["applied"] is True
    assert pricing["payload"]["amount"] == "1250.00"
    assert pricing["sources"][0]["corpus_version"] == "2026.09.03"
    assert pricing["sources"][0]["fact_id"] == "price.invoice-3way.senior-consultant.day-rate"
    chapter_text = json.dumps(framework["chapters"])
    assert "1250.00" in chapter_text
    assert "corpus 2026.09.03" in chapter_text
    assert "price.invoice-3way.senior-consultant.day-rate" in chapter_text


def test_fixture_mode_unknown_company_facts_are_open_questions() -> None:
    opportunity_id = _seed(name="Warehouse pallet labeling")
    store = get_memory_store()
    framework = generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=USER_ID,
        execution_mode="fixture",
    )
    meta = framework["generation_meta"]["company_facts"]
    assert meta["applied"] is False
    assert any("Borek pricing is not uniquely supported" in item["description"] for item in framework["open_items"])
    assert "1250" not in str(meta["lookups"])


def test_live_mode_passes_company_facts_and_never_ingests(monkeypatch: object) -> None:
    opportunity_id = _seed(name="Invoice 3-Way Match")
    store = get_memory_store()
    seen: dict[str, Any] = {}

    def ingest(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("Framework generation must not call knowledge ingest")

    def extract(turns: list[Any], identity: Any, *, redact: bool, **_kwargs: Any) -> dict[str, Any]:
        return {"facts": [], "conversation_id": "C1"}

    def generate(models: list[Any], **kwargs: Any) -> dict[str, Any]:
        seen["company_facts"] = kwargs.get("company_facts")
        return {"title": "Live", "chapters": [], "open_items": [], "generation_meta": {}}

    monkeypatch.setattr(store, "ingest_approved_corpus", ingest)
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
    facts = seen["company_facts"]
    pricing = next(item for item in facts["lookups"] if item["kind"] == "pricing")
    assert pricing["payload"]["amount"] == "1250.00"
    assert pricing["sources"][0]["document_id"] == "RC-DUMMY-2026-Q3"
