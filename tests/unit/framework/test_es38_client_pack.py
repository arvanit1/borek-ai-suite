"""ES-38 — additional_client_information is used as structured context, never invented."""

from __future__ import annotations

import json
from pathlib import Path

from services.framework.client_pack import (
    ALLOWED_CLIENT_PACK_FIELDS,
    apply_client_pack_to_skeleton,
    attach_client_pack_meta,
    format_client_pack_for_prompt,
    normalize_client_pack,
)
from services.framework.pipeline import generate_customer_framework
from services.knowledge_model.extraction import extract_knowledge_model
from services.transcript.conversation_ids import TranscriptIdentity
from services.transcript.speaker_turns import SpeakerTurn

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"
PACK = {
    "location_requirements": ["EU hosting"],
    "constraints": ["Go-live by Q4"],
    "contacts": [{"name": "Ada Lovelace", "role": "Sponsor", "invented": "drop-me"}],
    "priorities": ["Accuracy"],
    "notes": "Procurement review is pending.",
    "made_up_field": "must not survive",
}


def test_normalize_drops_unknown_fields_and_empty_pack() -> None:
    assert normalize_client_pack(None) is None
    assert normalize_client_pack({}) is None
    assert normalize_client_pack({"made_up_field": "x"}) is None
    normalized = normalize_client_pack(PACK)
    assert normalized is not None
    assert set(normalized) <= set(ALLOWED_CLIENT_PACK_FIELDS)
    assert "made_up_field" not in normalized
    assert "invented" not in normalized["contacts"][0]
    assert normalized["contacts"][0]["name"] == "Ada Lovelace"


def test_missing_client_pack_leaves_skeleton_unchanged() -> None:
    skeleton = {"constraints": ["ERP access"], "open_items": [], "people": [], "requirements": []}
    assert apply_client_pack_to_skeleton(skeleton, None) == skeleton
    prompt = format_client_pack_for_prompt(None)
    assert prompt == ""


def test_client_pack_merges_into_skeleton_and_meta() -> None:
    skeleton = apply_client_pack_to_skeleton(
        {"constraints": [], "open_items": [], "people": [], "requirements": []},
        PACK,
    )
    assert "EU hosting" in skeleton["constraints"]
    assert "Go-live by Q4" in skeleton["constraints"]
    assert "Ada Lovelace (Sponsor)" in skeleton["people"]
    assert any("Procurement review is pending." in item["description"] for item in skeleton["open_items"])
    framework = attach_client_pack_meta({"generation_meta": {}}, PACK)
    assert framework["generation_meta"]["client_pack"]["applied"] is True
    assert framework["generation_meta"]["client_pack"]["payload"]["priorities"] == ["Accuracy"]
    assert "made_up_field" not in framework["generation_meta"]["client_pack"]["payload"]


def test_extraction_prompt_includes_pack_only_when_present() -> None:
    seen: dict[str, str] = {}
    fixture = json.loads((FIXTURES / "knowledge_model.minimal.json").read_text(encoding="utf-8"))

    def capture(system: str, user: str, schema: dict) -> dict:
        seen["user"] = user
        return fixture

    identity = TranscriptIdentity("opp-1", "t-1", "C1")
    turns = [SpeakerTurn(0, "Sandra", "We match invoices in the ERP.")]
    extract_knowledge_model(turns, identity, complete=capture)
    assert "CLIENT_PACK_BEGIN" not in seen["user"]
    extract_knowledge_model(turns, identity, complete=capture, client_pack=PACK)
    assert "CLIENT_PACK_BEGIN" in seen["user"]
    assert "EU hosting" in seen["user"]
    assert "made_up_field" not in seen["user"]


def test_generate_framework_without_pack_matches_today() -> None:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    baseline = generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    with_none = generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
        client_pack=None,
    )
    assert with_none["generation_meta"]["client_pack"]["applied"] is False
    assert with_none["open_items"] == baseline["open_items"]


def test_generate_framework_uses_client_pack_without_inventing_fields() -> None:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    framework = generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
        client_pack=PACK,
    )
    meta = framework["generation_meta"]["client_pack"]
    assert meta["applied"] is True
    assert meta["source"] == "additional_client_information"
    assert "made_up_field" not in meta["payload"]
    descriptions = " ".join(item["description"] for item in framework["open_items"])
    assert "EU hosting" in descriptions
    assert "Go-live by Q4" in descriptions
    assert "never mentioned in the source" not in descriptions
