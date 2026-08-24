"""AT-3: SlideSpec base schema contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "slide_spec" / "base.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "fixtures" / "slide_spec" / "architecture_01.minimal.json"
LAYOUT_REGISTRY_PATH = CONTRACTS_DIR / "layout_registry.json"

SLIDE_SPEC_BASE_REQUIRED_FIELDS = {"schema_version", "layoutId", "title", "sourceChapterIds"}


@pytest.fixture(scope="module")
def slide_spec_base_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def architecture_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.is_file()


def test_at3_backlog_done_when_fields_are_required(slide_spec_base_schema: dict) -> None:
    """Maps to AT-3 done-when: shared base shape including sourceChapterIds."""
    base = slide_spec_base_schema
    assert SLIDE_SPEC_BASE_REQUIRED_FIELDS <= set(base["required"])
    assert "sourceChapterIds" in base["required"]
    assert SLIDE_SPEC_BASE_REQUIRED_FIELDS <= set(base["properties"].keys())
    assert slide_spec_base_schema["$defs"]["SlideSpecBase"]["$ref"] == "#"


def test_section14_architecture_example_validates(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    jsonschema.validate(instance=architecture_fixture, schema=slide_spec_base_schema)


def test_section14_example_field_values(architecture_fixture: dict) -> None:
    assert architecture_fixture["layoutId"] == "ARCHITECTURE_01"
    assert architecture_fixture["sourceChapterIds"] == ["6", "7"]
    assert architecture_fixture["sectionLabel"] == "ARCHITECTURE"
    assert len(architecture_fixture["components"]) == 4


def test_schema_rejects_missing_source_chapter_ids(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    invalid = {**architecture_fixture}
    del invalid["sourceChapterIds"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=slide_spec_base_schema)


def test_schema_rejects_empty_source_chapter_ids(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    invalid = {**architecture_fixture, "sourceChapterIds": []}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=slide_spec_base_schema)


def test_schema_rejects_invalid_source_chapter_id(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    invalid = {**architecture_fixture, "sourceChapterIds": ["chapter_6"]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=slide_spec_base_schema)


def test_schema_rejects_unknown_layout_id(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    invalid = {**architecture_fixture, "layoutId": "COOL_TIMELINE_BLUE_27"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=slide_spec_base_schema)


def test_schema_rejects_missing_title(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    invalid = {**architecture_fixture}
    del invalid["title"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=slide_spec_base_schema)


def test_schema_rejects_missing_layout_id(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    invalid = {**architecture_fixture}
    del invalid["layoutId"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=slide_spec_base_schema)


def test_schema_rejects_wrong_schema_version(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    invalid = {**architecture_fixture, "schema_version": "2.0"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=slide_spec_base_schema)


def test_layout_specific_fields_allowed_on_base(
    slide_spec_base_schema: dict, architecture_fixture: dict
) -> None:
    """Layout schemas add fields like components; base uses additionalProperties: true."""
    jsonschema.validate(instance=architecture_fixture, schema=slide_spec_base_schema)


def test_optional_base_fields_not_required(slide_spec_base_schema: dict) -> None:
    minimal = {
        "schema_version": "1.0",
        "layoutId": "COVER_01",
        "title": "Automation Proposal",
        "sourceChapterIds": ["1"],
    }
    jsonschema.validate(instance=minimal, schema=slide_spec_base_schema)


def test_layout_ids_align_with_layout_registry() -> None:
    registry = json.loads(LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    registry_ids = set(registry["layouts"].keys())
    schema_ids = set(schema["$defs"]["LayoutId"]["enum"])
    assert registry_ids == schema_ids
