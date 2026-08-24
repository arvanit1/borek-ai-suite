"""BT-4..BT-8: Group A layout-specific SlideSpec contract tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.parse import urljoin

import jsonschema
import pytest
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
SCHEMA_DIR = CONTRACTS_DIR / "slide_spec" / "group_a"
FIXTURE_DIR = CONTRACTS_DIR / "fixtures" / "slide_spec" / "group_a"
BASE_SCHEMA_PATH = CONTRACTS_DIR / "slide_spec" / "base.schema.json"
LAYOUT_REGISTRY_PATH = CONTRACTS_DIR / "layout_registry.json"

BASE_FIELDS = {
    "schema_version",
    "slideId",
    "layoutId",
    "sectionLabel",
    "title",
    "subtitle",
    "sourceChapterIds",
}

CASES = {
    "cover_01": {
        "layout_id": "COVER_01",
        "required_field": "statBadges",
        "invalid_type": "not-a-list",
        "malformed": [{"value": "85%"}],
    },
    "context_01": {
        "layout_id": "CONTEXT_01",
        "required_field": "problem",
        "invalid_type": "not-a-content-block",
        "malformed": {"title": "Problem"},
    },
    "problem_solution_01": {
        "layout_id": "PROBLEM_SOLUTION_01",
        "required_field": "solution",
        "invalid_type": ["not", "a", "content", "block"],
        "malformed": {"description": "Missing a title"},
    },
    "scope_01": {
        "layout_id": "SCOPE_01",
        "required_field": "included",
        "invalid_type": "not-a-list",
        "malformed": [{"text": "Items must be strings"}],
    },
    "requirements_matrix_01": {
        "layout_id": "REQUIREMENTS_MATRIX_01",
        "required_field": "requirements",
        "invalid_type": {"not": "a list"},
        "malformed": [{"category": "A", "title": "Requirement", "status": "green"}],
    },
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


BASE_SCHEMA = _load_json(BASE_SCHEMA_PATH)
LAYOUT_REGISTRY = _load_json(LAYOUT_REGISTRY_PATH)


def _schema(case_name: str) -> dict:
    return _load_json(SCHEMA_DIR / f"{case_name}.schema.json")


def _fixture(case_name: str, variant: str) -> dict:
    return _load_json(FIXTURE_DIR / f"{case_name}.{variant}.json")


def _validator(case_name: str) -> jsonschema.Draft202012Validator:
    schema = _schema(case_name)
    base_resource = Resource.from_contents(BASE_SCHEMA)
    relative_base_uri = urljoin(schema["$id"], "../base.schema.json")
    registry = (
        Registry()
        .with_resource(BASE_SCHEMA["$id"], base_resource)
        .with_resource(relative_base_uri, base_resource)
    )
    return jsonschema.Draft202012Validator(schema, registry=registry)


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_schema_is_valid_draft_2020_12(case_name: str) -> None:
    jsonschema.Draft202012Validator.check_schema(_schema(case_name))


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_schema_extends_base_and_pins_registered_layout(case_name: str) -> None:
    schema = _schema(case_name)
    layout_id = CASES[case_name]["layout_id"]

    assert schema["allOf"][0]["$ref"] == "../base.schema.json#/$defs/SlideSpecBase"
    assert schema["properties"]["layoutId"]["const"] == layout_id
    assert layout_id in LAYOUT_REGISTRY["layouts"]
    assert BASE_FIELDS <= set(schema["properties"])
    assert {"schema_version", "layoutId", "title", "sourceChapterIds"} <= set(schema["required"])
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("case_name", CASES)
@pytest.mark.parametrize("variant", ["minimal", "realistic"])
def test_group_a_valid_fixtures(case_name: str, variant: str) -> None:
    _validator(case_name).validate(_fixture(case_name, variant))


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_rejects_missing_layout_required_field(case_name: str) -> None:
    payload = _fixture(case_name, "minimal")
    del payload[CASES[case_name]["required_field"]]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_rejects_wrong_layout_id(case_name: str) -> None:
    payload = {**_fixture(case_name, "minimal"), "layoutId": "ARCHITECTURE_01"}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_rejects_invalid_layout_field_type(case_name: str) -> None:
    payload = _fixture(case_name, "minimal")
    payload[CASES[case_name]["required_field"]] = CASES[case_name]["invalid_type"]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_rejects_malformed_nested_or_list_content(case_name: str) -> None:
    payload = _fixture(case_name, "minimal")
    payload[CASES[case_name]["required_field"]] = CASES[case_name]["malformed"]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_rejects_unexpected_root_structure(case_name: str) -> None:
    payload = {**_fixture(case_name, "minimal"), "x": 2.5, "color": "#00FF00"}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_a_enforces_base_source_chapter_ids(case_name: str) -> None:
    missing = _fixture(case_name, "minimal")
    del missing["sourceChapterIds"]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(missing)

    malformed = {**_fixture(case_name, "minimal"), "sourceChapterIds": ["chapter_1"]}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(malformed)


def test_scope_lists_support_independent_item_counts() -> None:
    payload = _fixture("scope_01", "realistic")
    assert len(payload["included"]) == 5
    assert len(payload["later"]) == 2
    _validator("scope_01").validate(payload)


def test_requirements_status_is_semantic_and_rejects_arbitrary_color() -> None:
    schema = _schema("requirements_matrix_01")
    status = schema["$defs"]["RequirementItem"]["properties"]["status"]
    assert status["enum"] == ["included", "partial", "later"]

    payload = copy.deepcopy(_fixture("requirements_matrix_01", "minimal"))
    payload["requirements"][0]["color"] = "#00FF00"
    with pytest.raises(jsonschema.ValidationError):
        _validator("requirements_matrix_01").validate(payload)


def test_cover_rejects_malformed_stat_badge_extra_field() -> None:
    payload = copy.deepcopy(_fixture("cover_01", "minimal"))
    payload["statBadges"][0]["fontSize"] = 24
    with pytest.raises(jsonschema.ValidationError):
        _validator("cover_01").validate(payload)


@pytest.mark.parametrize("case_name", ["context_01", "problem_solution_01"])
def test_content_blocks_reject_unexpected_style_fields(case_name: str) -> None:
    payload = copy.deepcopy(_fixture(case_name, "minimal"))
    payload["problem"]["color"] = "primary"
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)
