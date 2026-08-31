"""MS-1..MS-5: Group C layout-specific SlideSpec contract tests."""

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
SCHEMA_DIR = CONTRACTS_DIR / "slide_spec" / "group_c"
FIXTURE_DIR = CONTRACTS_DIR / "fixtures" / "slide_spec"
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
    "architecture_01": {
        "layout_id": "ARCHITECTURE_01",
        "required_field": "components",
    },
    "compliance_01": {
        "layout_id": "COMPLIANCE_01",
        "required_field": "items",
    },
    "success_metrics_01": {
        "layout_id": "SUCCESS_METRICS_01",
        "required_field": "criteria",
    },
    "open_questions_01": {
        "layout_id": "OPEN_QUESTIONS_01",
        "required_field": "left",
    },
    "next_steps_01": {
        "layout_id": "NEXT_STEPS_01",
        "required_field": "steps",
    },
}

SUCCESS_METRICS_MONEY_FIELDS = ("amount", "currency", "price", "roi", "value")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


BASE_SCHEMA = _load_json(BASE_SCHEMA_PATH)
LAYOUT_REGISTRY = _load_json(LAYOUT_REGISTRY_PATH)


def _schema(case_name: str) -> dict:
    return _load_json(SCHEMA_DIR / f"{case_name}.schema.json")


def _fixture(case_name: str) -> dict:
    return _load_json(FIXTURE_DIR / f"{case_name}.minimal.json")


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
def test_group_c_schema_is_valid_draft_2020_12(case_name: str) -> None:
    jsonschema.Draft202012Validator.check_schema(_schema(case_name))


@pytest.mark.parametrize("case_name", CASES)
def test_group_c_schema_extends_base_and_pins_registered_layout(case_name: str) -> None:
    schema = _schema(case_name)
    layout_id = CASES[case_name]["layout_id"]

    assert schema["allOf"][0]["$ref"] == "../base.schema.json#/$defs/SlideSpecBase"
    assert schema["properties"]["layoutId"]["const"] == layout_id
    assert layout_id in LAYOUT_REGISTRY["layouts"]
    assert BASE_FIELDS <= set(schema["properties"])
    assert {"schema_version", "layoutId", "title", "sourceChapterIds"} <= set(schema["required"])
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("case_name", CASES)
def test_group_c_valid_fixtures(case_name: str) -> None:
    _validator(case_name).validate(_fixture(case_name))


@pytest.mark.parametrize("case_name", CASES)
def test_group_c_realistic_fixtures(case_name: str) -> None:
    payload = _load_json(FIXTURE_DIR / "group_c" / f"{case_name}.realistic.json")
    _validator(case_name).validate(payload)


def test_architecture_existing_fixture_validates() -> None:
    _validator("architecture_01").validate(_fixture("architecture_01"))


def test_success_metrics_schema_has_no_money_fields() -> None:
    schema = _schema("success_metrics_01")
    criterion_fields = set(schema["$defs"]["SuccessCriterion"]["properties"])
    assert criterion_fields == {"title", "description"}
    root_fields = set(schema["properties"])
    assert not set(SUCCESS_METRICS_MONEY_FIELDS) & root_fields
    assert not set(SUCCESS_METRICS_MONEY_FIELDS) & criterion_fields


@pytest.mark.parametrize("case_name", CASES)
def test_group_c_rejects_missing_layout_required_field(case_name: str) -> None:
    payload = _fixture(case_name)
    del payload[CASES[case_name]["required_field"]]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_c_rejects_wrong_layout_id(case_name: str) -> None:
    payload = {**_fixture(case_name), "layoutId": "COVER_01"}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(payload)


@pytest.mark.parametrize("case_name", CASES)
def test_group_c_enforces_base_source_chapter_ids(case_name: str) -> None:
    missing = _fixture(case_name)
    del missing["sourceChapterIds"]
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(missing)

    malformed = {**_fixture(case_name), "sourceChapterIds": ["chapter_6"]}
    with pytest.raises(jsonschema.ValidationError):
        _validator(case_name).validate(malformed)


@pytest.mark.parametrize("case_name", CASES)
def test_group_c_re_lists_optional_shared_field_provenance(case_name: str) -> None:
    schema = _schema(case_name)
    assert schema["properties"]["fieldProvenance"]["$ref"] == (
        "../base.schema.json#/properties/fieldProvenance"
    )
    assert "fieldProvenance" not in schema["required"]

    payload = _fixture(case_name)
    assert payload["fieldProvenance"]
    _validator(case_name).validate(payload)

    legacy_compatible = copy.deepcopy(payload)
    del legacy_compatible["fieldProvenance"]
    _validator(case_name).validate(legacy_compatible)
