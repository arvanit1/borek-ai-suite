"""JJ-1..JJ-4: Group B layout-specific SlideSpec contract tests."""

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
SCHEMA_DIR = CONTRACTS_DIR / "slide_spec" / "group_b"
FIXTURE_DIR = CONTRACTS_DIR / "fixtures" / "slide_spec" / "group_b"
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
    "fieldProvenance",
}

CASES = {
    "process_flow_01": {
        "layout_id": "PROCESS_FLOW_01",
        "required_field": "phases",
        "invalid_type": "not-a-list",
        "malformed": [{"name": "Receive invoice"}],
    },
    "timeline_01": {
        "layout_id": "TIMELINE_01",
        "required_field": "phases",
        "invalid_type": "not-a-list",
        "malformed": [{"name": "Discover"}],
    },
    "milestones_01": {
        "layout_id": "MILESTONES_01",
        "required_field": "milestones",
        "invalid_type": "not-a-list",
        "malformed": [{"description": "Missing a name"}],
    },
    "team_fte_01": {
        "layout_id": "TEAM_FTE_01",
        "required_field": "roles",
        "invalid_type": "not-a-list",
        "malformed": [{"role": "Process owner"}],
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
def test_group_b_schema_is_valid_draft_2020_12(case_name: str) -> None:
    jsonschema.Draft202012Validator.check_schema(_schema(case_name))


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_schema_extends_base_and_pins_registered_layout(case_name: str) -> None:
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
def test_group_b_valid_fixtures(case_name: str, variant: str) -> None:
    _validator(case_name).validate(_fixture(case_name, variant))


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_rejects_missing_layout_required_field(case_name: str) -> None:
    payload = _fixture(case_name, "minimal")
    del payload[CASES[case_name]["required_field"]]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_rejects_wrong_layout_id(case_name: str) -> None:
    payload = {**_fixture(case_name, "minimal"), "layoutId": "ARCHITECTURE_01"}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_rejects_invalid_layout_field_type(case_name: str) -> None:
    payload = _fixture(case_name, "minimal")
    payload[CASES[case_name]["required_field"]] = CASES[case_name]["invalid_type"]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_rejects_malformed_nested_or_list_content(case_name: str) -> None:
    payload = _fixture(case_name, "minimal")
    payload[CASES[case_name]["required_field"]] = CASES[case_name]["malformed"]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_rejects_unexpected_root_structure(case_name: str) -> None:
    payload = {**_fixture(case_name, "minimal"), "x": 2.5, "color": "#00FF00"}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_enforces_base_source_chapter_ids(case_name: str) -> None:
    missing = _fixture(case_name, "minimal")
    del missing["sourceChapterIds"]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(missing)

    malformed = {**_fixture(case_name, "minimal"), "sourceChapterIds": ["chapter_10"]}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(malformed)


@pytest.mark.parametrize("case_name", CASES)
def test_group_b_re_lists_optional_shared_field_provenance(case_name: str) -> None:
    schema = _schema(case_name)
    assert schema["properties"]["fieldProvenance"]["$ref"] == (
        "../base.schema.json#/properties/fieldProvenance"
    )
    assert "fieldProvenance" not in schema["required"]

    payload = _fixture(case_name, "minimal")
    assert payload["fieldProvenance"]
    _validator(case_name).validate(payload)

    legacy_compatible = copy.deepcopy(payload)
    del legacy_compatible["fieldProvenance"]
    _validator(case_name).validate(legacy_compatible)


def test_process_flow_requires_numbered_name_and_description() -> None:
    payload = copy.deepcopy(_fixture("process_flow_01", "minimal"))
    payload["phases"][0]["number"] = 0
    with pytest.raises(jsonschema.ValidationError):
        _validator("process_flow_01").validate(payload)

    payload = copy.deepcopy(_fixture("process_flow_01", "minimal"))
    payload["phases"][0]["fontSize"] = 18
    with pytest.raises(jsonschema.ValidationError):
        _validator("process_flow_01").validate(payload)


def test_timeline_keeps_phases_and_milestones_as_related_lists() -> None:
    payload = _fixture("timeline_01", "realistic")
    phase_ids = {phase["id"] for phase in payload["phases"]}
    assert len(payload["phases"]) == 4
    assert len(payload["milestones"]) == 4
    assert all(milestone["phaseId"] in phase_ids for milestone in payload["milestones"])
    _validator("timeline_01").validate(payload)

    missing_milestones = copy.deepcopy(_fixture("timeline_01", "minimal"))
    del missing_milestones["milestones"]
    with pytest.raises(jsonschema.ValidationError):
        _validator("timeline_01").validate(missing_milestones)


def test_timeline_milestone_requires_phase_id() -> None:
    payload = copy.deepcopy(_fixture("timeline_01", "minimal"))
    del payload["milestones"][0]["phaseId"]
    with pytest.raises(jsonschema.ValidationError):
        _validator("timeline_01").validate(payload)


def test_milestones_standalone_rejects_timeline_phase_id() -> None:
    schema = _schema("milestones_01")
    properties = schema["$defs"]["MilestoneItem"]["properties"]
    assert "phaseId" not in properties
    assert schema["required"] == [
        "schema_version",
        "layoutId",
        "title",
        "sourceChapterIds",
        "milestones",
    ]

    payload = copy.deepcopy(_fixture("milestones_01", "minimal"))
    payload["milestones"][0]["phaseId"] = "p1"
    with pytest.raises(jsonschema.ValidationError):
        _validator("milestones_01").validate(payload)


def test_team_fte_requires_role_cards_and_summary_row() -> None:
    payload = copy.deepcopy(_fixture("team_fte_01", "minimal"))
    del payload["summary"]
    with pytest.raises(jsonschema.ValidationError):
        _validator("team_fte_01").validate(payload)

    payload = copy.deepcopy(_fixture("team_fte_01", "minimal"))
    payload["roles"][0]["color"] = "primary"
    with pytest.raises(jsonschema.ValidationError):
        _validator("team_fte_01").validate(payload)


def test_team_fte_fte_is_a_display_string() -> None:
    payload = copy.deepcopy(_fixture("team_fte_01", "minimal"))
    payload["roles"][0]["fte"] = 0.3
    with pytest.raises(jsonschema.ValidationError):
        _validator("team_fte_01").validate(payload)
