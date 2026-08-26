"""ES-5 — transcript → KnowledgeModel extraction (Claude mocked)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.knowledge_model.extraction import (
    KNOWLEDGE_BUCKETS,
    PROMPT_VERSION,
    KnowledgeExtractionError,
    extract_knowledge_model,
)
from services.transcript.conversation_ids import TranscriptIdentity, allocate_transcript_identity
from services.transcript.speaker_turns import SpeakerTurn, split_speaker_turns

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "contracts"
    / "fixtures"
    / "knowledge_model.minimal.json"
)


def _identity() -> TranscriptIdentity:
    return allocate_transcript_identity("00000000-0000-4000-8000-000000000001")


def _complete_from_fixture(system: str, user: str, schema: dict) -> dict:
    assert "framework-extraction:v1" in system
    assert "turn:0" in user
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_extraction_stamps_es3_ids_and_all_buckets() -> None:
    identity = _identity()
    turns = [
        SpeakerTurn(0, "Sandra", "We match invoices in the ERP. Call sandra@client.de"),
    ]
    model = extract_knowledge_model(turns, identity, redact=True, complete=_complete_from_fixture)

    assert model["opportunity_id"] == identity.opportunity_id
    assert model["transcript_id"] == identity.transcript_id
    assert model["conversation_id"] == identity.conversation_id
    assert model["prompt_version"] == PROMPT_VERSION
    for bucket in KNOWLEDGE_BUCKETS:
        assert isinstance(model[bucket], list)
    assert model["facts"]
    assert model["named_systems"][0]["statement"] == "ERP"


def test_redacted_text_is_what_claude_sees() -> None:
    seen: dict[str, str] = {}

    def capture(system: str, user: str, schema: dict) -> dict:
        seen["user"] = user
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    identity = _identity()
    turns = split_speaker_turns(
        "call.txt",
        b"Sandra: Email sandra@client.de about the ERP.",
    )
    extract_knowledge_model(turns, identity, redact=True, complete=capture)
    assert "sandra@client.de" not in seen["user"]
    assert "[EMAIL]" in seen["user"]
    assert "SPEAKER_1" in seen["user"]


def test_empty_turns_are_rejected() -> None:
    with pytest.raises(KnowledgeExtractionError):
        extract_knowledge_model([], _identity(), complete=_complete_from_fixture)


def test_invalid_model_from_claude_fails_validation() -> None:
    def bad_complete(system: str, user: str, schema: dict) -> dict:
        return {
            "facts": [
                {
                    "statement": 12,
                    "origin": "SOURCE_FACT",
                    "confidence": "high",
                    "source_refs": [
                        {
                            "conversation_id": "C1",
                            "speaker_role": "Sandra",
                            "excerpt_pointer": "turn:0",
                        }
                    ],
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
        extract_knowledge_model(
            [SpeakerTurn(0, "Sandra", "ERP matching is slow.")],
            _identity(),
            complete=bad_complete,
        )
    assert "schema validation" in exc_info.value.user_message.lower()


def test_claude_shape_quirks_are_coerced() -> None:
    def messy_complete(system: str, user: str, schema: dict) -> dict:
        return {
            "facts": [
                {
                    "statement": "Invoices are matched in the ERP.",
                    "origin": "source_fact",
                    "confidence": "High",
                    "source_ref": {
                        "conversation_id": "c1",
                        "speaker": "Sandra",
                        "excerpt_pointer": 0,
                    },
                }
            ],
            "conflicts": [{"topic": "x", "values": ["a"], "source_ids": [], "requires_clarification": False}],
        }

    model = extract_knowledge_model(
        [SpeakerTurn(0, "Sandra", "ERP matching is slow.")],
        _identity(),
        complete=messy_complete,
    )
    fact = model["facts"][0]
    assert fact["origin"] == "SOURCE_FACT"
    assert fact["confidence"] == "high"
    assert fact["source_refs"][0]["conversation_id"] == "C1"
    assert fact["source_refs"][0]["excerpt_pointer"] == "turn:0"
    assert fact["source_refs"][0]["speaker_role"] == "Sandra"
    assert all(isinstance(model[bucket], list) for bucket in KNOWLEDGE_BUCKETS)


def test_pointer_outside_transcript_fails_es6() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["facts"][0]["source_refs"][0]["excerpt_pointer"] = "turn:9"

    def complete(system: str, user: str, schema: dict) -> dict:
        return payload

    with pytest.raises(KnowledgeExtractionError) as exc_info:
        extract_knowledge_model(
            [SpeakerTurn(0, "Sandra", "ERP matching is slow.")],
            _identity(),
            complete=complete,
        )
    assert "turn:9" in exc_info.value.user_message
