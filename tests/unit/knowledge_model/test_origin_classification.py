"""ES-7 — origin and confidence on every knowledge entry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.knowledge_model.origin_classification import (
    ORIGIN_VALUES,
    OriginClassificationError,
    validate_origins,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "contracts"
    / "fixtures"
    / "knowledge_model.minimal.json"
)


def _model() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_asserts_each_origin_type() -> None:
    model = _model()
    found = {
        entry["origin"]
        for bucket in (
            "facts",
            "stated_requirements",
            "constraints",
            "named_systems",
            "named_rules",
            "named_exceptions",
            "people_and_roles",
            "timeline_mentions",
            "risks",
            "unknowns",
        )
        for entry in model.get(bucket) or []
    }
    assert found == ORIGIN_VALUES
    validate_origins(model)


def test_missing_origin_fails() -> None:
    model = _model()
    model["facts"][0].pop("origin")
    with pytest.raises(OriginClassificationError) as exc_info:
        validate_origins(model)
    assert "origin" in exc_info.value.user_message.lower()


def test_invalid_confidence_fails() -> None:
    model = _model()
    model["facts"][0]["confidence"] = "certain"
    with pytest.raises(OriginClassificationError) as exc_info:
        validate_origins(model)
    assert "confidence" in exc_info.value.user_message.lower()
