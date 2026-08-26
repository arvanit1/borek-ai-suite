"""ES-31 — reject + retry on missing source_refs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.synthesis import FrameworkSynthesisError, synthesize_customer_draft
from services.knowledge_model.extraction import KnowledgeExtractionError, extract_knowledge_model
from services.knowledge_model.source_refs import SourceRefViolation
from services.transcript.conversation_ids import TranscriptIdentity
from services.transcript.speaker_turns import SpeakerTurn
from services.validation.schema_retry import (
    MAX_SOURCE_REF_RETRIES,
    SourceRefRetryError,
    require_valid_source_refs,
    run_with_source_ref_retry,
)

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


def test_es31_retries_once_then_succeeds() -> None:
    attempts: list[str | None] = []

    def call(feedback: str | None) -> dict[str, int]:
        attempts.append(feedback)
        if feedback is None:
            return {"value": 1}
        return {"value": 2}

    def collect(payload: dict[str, int]) -> list[SourceRefViolation]:
        if payload["value"] == 1:
            return [SourceRefViolation("facts[0]", "missing source_refs")]
        return []

    payload, count = require_valid_source_refs(call=call, collect_violations=collect)
    assert payload == {"value": 2}
    assert count == 2
    assert attempts == [None, attempts[1]]
    assert attempts[1] is not None
    assert "Fix these locations" in attempts[1]


def test_es31_fails_after_one_retry() -> None:
    def call(_feedback: str | None) -> dict[str, str]:
        return {"status": "bad"}

    def collect(_payload: dict[str, str]) -> list[SourceRefViolation]:
        return [SourceRefViolation("facts[0]", "missing source_refs")]

    with pytest.raises(SourceRefRetryError) as exc_info:
        require_valid_source_refs(call=call, collect_violations=collect)
    assert exc_info.value.attempts == MAX_SOURCE_REF_RETRIES + 1
    assert "after 2 attempts" in exc_info.value.user_message


def test_es31_extraction_retries_missing_source_refs() -> None:
    turns = [
        SpeakerTurn(0, "Sandra", "We match invoices in the ERP."),
    ]
    identity = TranscriptIdentity(
        opportunity_id="OPP-1",
        transcript_id="T-1",
        conversation_id="C1",
    )
    calls: list[str | None] = []

    def complete(system: str, user: str, schema: dict) -> dict:
        calls.append("RETRY" if "RETRY" in user else None)
        model = {
            "facts": [
                {
                    "statement": "Invoices are matched in the ERP.",
                    "origin": "SOURCE_FACT",
                    "confidence": "high",
                    "source_refs": [],
                }
            ],
        }
        for bucket in (
            "stated_requirements",
            "constraints",
            "named_systems",
            "named_rules",
            "named_exceptions",
            "people_and_roles",
            "timeline_mentions",
            "risks",
            "unknowns",
        ):
            model[bucket] = []
        if calls[-1] is not None:
            model["facts"][0]["source_refs"] = [
                {
                    "conversation_id": "C1",
                    "speaker_role": "Sandra",
                    "excerpt_pointer": "turn:0",
                }
            ]
        return model

    model = extract_knowledge_model(turns, identity, complete=complete)
    assert model["facts"][0]["source_refs"][0]["excerpt_pointer"] == "turn:0"
    assert len(calls) == 2


def test_es31_extraction_fails_when_retry_still_missing_refs() -> None:
    turns = [SpeakerTurn(0, "Sandra", "We match invoices in the ERP.")]
    identity = TranscriptIdentity(
        opportunity_id="OPP-1",
        transcript_id="T-1",
        conversation_id="C1",
    )

    def complete(system: str, user: str, schema: dict) -> dict:
        return {
            "facts": [
                {
                    "statement": "Invoices are matched in the ERP.",
                    "origin": "SOURCE_FACT",
                    "confidence": "high",
                    "source_refs": [],
                }
            ],
            "stated_requirements": [],
            "constraints": [],
            "named_systems": [],
            "named_rules": [],
            "named_exceptions": [],
            "people_and_roles": [],
            "timeline_mentions": [],
            "risks": [],
            "unknowns": [],
        }

    with pytest.raises(KnowledgeExtractionError) as exc_info:
        extract_knowledge_model(turns, identity, complete=complete)
    assert "source_refs" in exc_info.value.user_message.lower()


def test_es31_synthesis_retries_missing_chapter_source_refs() -> None:
    base = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    calls: list[str | None] = []

    def complete(system: str, user: str, schema: dict) -> dict:
        calls.append("RETRY" if "RETRY" in user else None)
        draft = {
            "title": "Invoice 3-Way Match",
            "department": "Finance",
            "cover": {
                "tagline": "Customer framework report.",
                "sources_line": "Sources C6",
                "how_produced": "Generated from conversations.",
            },
            "kpis": [],
            "systems": [],
            "rules": [],
            "exceptions": [],
            "access_needs": [],
            "open_items": [],
            "chapters": [],
        }
        registry = json.loads(
            (FIXTURES.parent / "chapter_registry.json").read_text(encoding="utf-8")
        )
        for item in registry["chapters"]:
            draft["chapters"].append(
                {
                    "chapter_id": item["chapter_id"],
                    "title": item["title"],
                    "body": [{"block": "prose", "text": "Named in the conversations."}],
                    "source_refs": [],
                }
            )
        if calls[-1] is not None:
            for chapter in draft["chapters"]:
                chapter["source_refs"] = [
                    {
                        "conversation_id": "C6",
                        "speaker_role": "Sandra",
                        "excerpt_pointer": "turn:0",
                    }
                ]
        return draft

    result = synthesize_customer_draft(
        skeleton={"opportunity_id": "OPP-142", "title": "Invoice 3-Way Match", "conversation_ids": ["C6"]},
        engine_outputs={"quality_scores": {"opportunity_rating": 70}},
        complete=complete,
    )
    assert result["chapters"][0]["source_refs"][0]["conversation_id"] == "C6"
    assert len(calls) == 2


def test_es31_synthesis_fails_when_retry_still_missing_refs() -> None:
    registry = json.loads((FIXTURES.parent / "chapter_registry.json").read_text(encoding="utf-8"))

    def complete(system: str, user: str, schema: dict) -> dict:
        chapters = [
            {
                "chapter_id": item["chapter_id"],
                "title": item["title"],
                "body": [{"block": "prose", "text": "Named in the conversations."}],
                "source_refs": [],
            }
            for item in registry["chapters"]
        ]
        return {
            "title": "Invoice 3-Way Match",
            "department": "Finance",
            "cover": {
                "tagline": "Customer framework report.",
                "sources_line": "Sources C6",
                "how_produced": "Generated from conversations.",
            },
            "kpis": [],
            "systems": [],
            "rules": [],
            "exceptions": [],
            "access_needs": [],
            "open_items": [],
            "chapters": chapters,
        }

    with pytest.raises(FrameworkSynthesisError) as exc_info:
        synthesize_customer_draft(
            skeleton={"opportunity_id": "OPP-142", "title": "Invoice 3-Way Match"},
            engine_outputs={},
            complete=complete,
        )
    assert "source_refs" in exc_info.value.user_message.lower()


def test_run_with_source_ref_retry_returns_failed_result_without_raise() -> None:
    result = run_with_source_ref_retry(
        call=lambda _feedback: {"ok": False},
        collect_violations=lambda _payload: [SourceRefViolation("x", "missing")],
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.attempts == MAX_SOURCE_REF_RETRIES + 1
