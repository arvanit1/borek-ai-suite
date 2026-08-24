"""AT-1: FrameworkObject schema contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "framework_object.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "fixtures" / "framework_object.minimal.json"

REQUIRED_CHAPTER_IDS = [str(i) for i in range(14)]

# Technical plan section 7 - FrameworkObject top-level fields
SECTION7_TOP_LEVEL_FIELDS = {
    "schema_version",
    "opportunity_id",
    "title",
    "department",
    "status",
    "priority_rank",
    "quality_scores",
    "kpis",
    "systems",
    "rules",
    "exceptions",
    "access_needs",
    "evolution_stages",
    "open_items",
    "chapters",
    "version",
    "generated_from",
    "previous_version_id",
    "change_log",
    "created_at",
    "updated_at",
}

SECTION7_NESTED_TYPES = {
    "ConversationRef",
    "OpenItem",
    "KpiRecord",
    "SystemRecord",
    "RuleRecord",
    "ExceptionRecord",
    "AccessNeed",
    "EvolutionStage",
    "QualityScores",
    "Chapter",
}


@pytest.fixture(scope="module")
def framework_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def minimal_framework_object() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.is_file()


def test_schema_covers_section7_top_level_fields(framework_schema: dict) -> None:
    properties = set(framework_schema["properties"].keys())
    required = set(framework_schema["required"])
    assert SECTION7_TOP_LEVEL_FIELDS <= properties
    assert SECTION7_TOP_LEVEL_FIELDS <= required


def test_schema_covers_section7_nested_types(framework_schema: dict) -> None:
    defs = set(framework_schema["$defs"].keys())
    assert SECTION7_NESTED_TYPES <= defs


def test_minimal_fixture_validates(framework_schema: dict, minimal_framework_object: dict) -> None:
    jsonschema.validate(instance=minimal_framework_object, schema=framework_schema)


def test_schema_requires_fourteen_chapters(minimal_framework_object: dict) -> None:
    chapters = minimal_framework_object["chapters"]
    assert len(chapters) == 14
    assert [c["chapter_id"] for c in chapters] == REQUIRED_CHAPTER_IDS


def test_schema_rejects_wrong_chapter_count(framework_schema: dict, minimal_framework_object: dict) -> None:
    invalid = {**minimal_framework_object, "chapters": minimal_framework_object["chapters"][:13]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=framework_schema)


def test_schema_rejects_invalid_chapter_id(framework_schema: dict, minimal_framework_object: dict) -> None:
    chapters = [dict(c) for c in minimal_framework_object["chapters"]]
    chapters[0] = {**chapters[0], "chapter_id": "99"}
    invalid = {**minimal_framework_object, "chapters": chapters}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=framework_schema)


def test_schema_rejects_wrong_version(framework_schema: dict, minimal_framework_object: dict) -> None:
    invalid = {**minimal_framework_object, "schema_version": "2.0"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=framework_schema)


def test_schema_rejects_invalid_status(framework_schema: dict, minimal_framework_object: dict) -> None:
    invalid = {**minimal_framework_object, "status": "approved"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=framework_schema)


def test_schema_rejects_missing_quality_rationale_key(
    framework_schema: dict, minimal_framework_object: dict
) -> None:
    scores = dict(minimal_framework_object["quality_scores"])
    scores["rationale"] = {"opportunity_rating": "only one key"}
    invalid = {**minimal_framework_object, "quality_scores": scores}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=framework_schema)


def test_additive_fields_allowed_at_root(framework_schema: dict, minimal_framework_object: dict) -> None:
    extended = {**minimal_framework_object, "future_field": "ignored by strict consumers"}
    jsonschema.validate(instance=extended, schema=framework_schema)
