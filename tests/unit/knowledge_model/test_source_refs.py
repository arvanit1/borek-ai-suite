"""ES-6 — conversation_id + turn pointer required on every entry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.knowledge_model.source_refs import SourceRefError, validate_source_refs

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "contracts"
    / "fixtures"
    / "knowledge_model.minimal.json"
)


def _model() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_valid_fixture_passes() -> None:
    validate_source_refs(_model(), allowed_conversation_ids=["C1"], allowed_turn_indices=[0])


def test_missing_pointer_fails_validation() -> None:
    model = _model()
    model["facts"][0]["source_refs"][0].pop("excerpt_pointer")
    with pytest.raises(SourceRefError) as exc_info:
        validate_source_refs(model)
    assert "turn pointer" in exc_info.value.user_message.lower() or "excerpt_pointer" in exc_info.value.user_message


def test_empty_source_refs_fails() -> None:
    model = _model()
    model["facts"][0]["source_refs"] = []
    with pytest.raises(SourceRefError) as exc_info:
        validate_source_refs(model)
    assert "missing" in exc_info.value.user_message.lower()


def test_invalid_pointer_format_fails() -> None:
    model = _model()
    model["facts"][0]["source_refs"][0]["excerpt_pointer"] = "line-4"
    with pytest.raises(SourceRefError) as exc_info:
        validate_source_refs(model)
    assert "turn:" in exc_info.value.user_message


def test_turn_outside_transcript_fails_on_extract() -> None:
    model = _model()
    model["facts"][0]["source_refs"][0]["excerpt_pointer"] = "turn:9"
    with pytest.raises(SourceRefError) as exc_info:
        validate_source_refs(model, allowed_conversation_ids=["C1"], allowed_turn_indices=[0])
    assert "turn:9" in exc_info.value.user_message


def test_wrong_conversation_id_fails_on_extract() -> None:
    model = _model()
    model["facts"][0]["source_refs"][0]["conversation_id"] = "C9"
    with pytest.raises(SourceRefError) as exc_info:
        validate_source_refs(model, allowed_conversation_ids=["C1"], allowed_turn_indices=[0])
    assert "C9" in exc_info.value.user_message
