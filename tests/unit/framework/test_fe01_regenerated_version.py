"""Stage 1 FE-01: append-only single-chapter Framework regeneration."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.framework.regenerate_chapter import ChapterRegenError, build_regenerated_framework
from services.framework.synthesis import (
    ChapterSynthesisValidationError,
    FrameworkSynthesisError,
    synthesize_customer_chapter,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "framework_object.minimal.json"


def _framework() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_regenerated_version_changes_only_target_chapter() -> None:
    source = _framework()
    original = copy.deepcopy(source)
    replacement = copy.deepcopy(source["chapters"][3])
    replacement["body"] = [{"block": "prose", "text": "New evidence-grounded aim."}]

    result = build_regenerated_framework(
        source,
        "3",
        replacement,
        source_framework_version_id="source-row-id",
        new_version=2,
        now=lambda: datetime(2026, 9, 16, tzinfo=UTC),
    )

    assert source == original
    assert result["version"] == 2
    assert result["previous_version_id"] == "source-row-id"
    assert result["chapters"][3] == replacement
    assert result["chapters"][:3] == source["chapters"][:3]
    assert result["chapters"][4:] == source["chapters"][4:]


def test_regenerated_version_rejects_unchanged_chapter() -> None:
    source = _framework()

    with pytest.raises(ChapterRegenError, match="did not change"):
        build_regenerated_framework(
            source,
            "3",
            source["chapters"][3],
            source_framework_version_id="source-row-id",
            new_version=2,
        )


def test_chapter_synthesis_requests_and_validates_only_target_chapter() -> None:
    framework = _framework()
    calls: list[dict] = []
    knowledge_models = [
        {
            "facts": [
                {
                    "statement": "Success is measured by processing time.",
                    "origin": "SOURCE_FACT",
                    "confidence": 0.9,
                    "source_refs": [
                        {
                            "conversation_id": "C1",
                            "speaker_role": "operator",
                            "excerpt_pointer": "turn:0",
                        }
                    ],
                }
            ]
        }
    ]

    def complete(_system: str, _user: str, schema: dict) -> dict:
        calls.append(schema)
        return {
            "chapter_id": "3",
            "title": framework["chapters"][3]["title"],
            "body": [{"block": "prose", "text": "Processing time is the success measure."}],
            "source_refs": [
                {
                    "conversation_id": "C1",
                    "speaker_role": "operator",
                    "excerpt_pointer": "turn:0",
                }
            ],
        }

    chapter = synthesize_customer_chapter(
        framework=framework,
        knowledge_models=knowledge_models,
        chapter_id="3",
        complete=complete,
    )

    assert chapter["chapter_id"] == "3"
    assert calls[0]["properties"]["chapter_id"] == {"const": "3"}
    assert "chapters" not in calls[0]["properties"]


def test_chapter_synthesis_coerces_numeric_chapter_id() -> None:
    framework = _framework()
    title = framework["chapters"][11]["title"]

    def complete(_system: str, _user: str, _schema: dict) -> dict:
        return {
            "chapter_id": 11,
            "title": title,
            "body": [{"block": "prose", "text": "Three independent quality gates apply before go-live."}],
            "source_refs": [
                {
                    "conversation_id": "C1",
                    "speaker_role": "operator",
                    "excerpt_pointer": 0,
                }
            ],
        }

    chapter = synthesize_customer_chapter(
        framework=framework,
        knowledge_models=[
            {
                "facts": [
                    {
                        "statement": "Three independent quality gates apply before go-live.",
                        "source_refs": [
                            {
                                "conversation_id": "C1",
                                "speaker_role": "operator",
                                "excerpt_pointer": "turn:0",
                            }
                        ],
                    }
                ]
            }
        ],
        chapter_id="11",
        complete=complete,
    )

    assert chapter["chapter_id"] == "11"
    assert chapter["source_refs"][0]["excerpt_pointer"] == "turn:0"


def test_chapter_synthesis_rejects_reference_outside_knowledge_model() -> None:
    framework = _framework()

    def complete(_system: str, _user: str, _schema: dict) -> dict:
        return {
            "chapter_id": "3",
            "title": framework["chapters"][3]["title"],
            "body": [{"block": "prose", "text": "Unsupported claim."}],
            "source_refs": [
                {
                    "conversation_id": "C2",
                    "speaker_role": "operator",
                    "excerpt_pointer": "turn:9",
                }
            ],
        }

    with pytest.raises(FrameworkSynthesisError, match="does not match"):
        synthesize_customer_chapter(
            framework=framework,
            knowledge_models=[
                {
                    "facts": [
                        {
                            "statement": "Grounded fact.",
                            "source_refs": [
                                {
                                    "conversation_id": "C1",
                                    "speaker_role": "operator",
                                    "excerpt_pointer": "turn:0",
                                }
                            ],
                        }
                    ]
                }
            ],
            chapter_id="3",
            complete=complete,
        )


def test_chapter_validation_error_has_non_retryable_validation_code() -> None:
    error = ChapterSynthesisValidationError("invalid chapter")

    assert error.code == "FRAMEWORK_VALIDATION_FAILED"
    assert error.retryable is False
