"""JJ-23: EXECUTIVE_SUMMARY_01 SlideSpec contract tests."""

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
SCHEMA_PATH = CONTRACTS_DIR / "slide_spec" / "summary" / "executive_summary_01.schema.json"
FIXTURE_DIR = CONTRACTS_DIR / "fixtures" / "slide_spec" / "summary"
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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMA = _load_json(SCHEMA_PATH)
BASE_SCHEMA = _load_json(BASE_SCHEMA_PATH)
LAYOUT_REGISTRY = _load_json(LAYOUT_REGISTRY_PATH)


def _fixture(variant: str) -> dict:
    return _load_json(FIXTURE_DIR / f"executive_summary_01.{variant}.json")


def _validator() -> jsonschema.Draft202012Validator:
    base_resource = Resource.from_contents(BASE_SCHEMA)
    relative_base_uri = urljoin(SCHEMA["$id"], "../base.schema.json")
    registry = (
        Registry()
        .with_resource(BASE_SCHEMA["$id"], base_resource)
        .with_resource(relative_base_uri, base_resource)
    )
    return jsonschema.Draft202012Validator(SCHEMA, registry=registry)


def test_executive_summary_schema_is_valid_draft_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


def test_executive_summary_schema_extends_base_and_pins_registered_layout() -> None:
    assert SCHEMA["allOf"][0]["$ref"] == "../base.schema.json#/$defs/SlideSpecBase"
    assert SCHEMA["properties"]["layoutId"]["const"] == "EXECUTIVE_SUMMARY_01"
    assert "EXECUTIVE_SUMMARY_01" in LAYOUT_REGISTRY["layouts"]
    assert BASE_FIELDS <= set(SCHEMA["properties"])
    assert {"schema_version", "layoutId", "title", "sourceChapterIds", "headline", "highlights"} <= set(
        SCHEMA["required"]
    )
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize("variant", ["minimal", "realistic"])
def test_executive_summary_valid_fixtures(variant: str) -> None:
    _validator().validate(_fixture(variant))


def test_executive_summary_rejects_missing_required_fields() -> None:
    for field_name in ("headline", "highlights"):
        payload = _fixture("minimal")
        del payload[field_name]
        with pytest.raises(jsonschema.ValidationError):
            _validator().validate(payload)


def test_executive_summary_rejects_wrong_layout_id() -> None:
    payload = {**_fixture("minimal"), "layoutId": "COVER_01"}
    with pytest.raises(jsonschema.ValidationError):
        _validator().validate(payload)


def test_executive_summary_rejects_malformed_highlights() -> None:
    payload = _fixture("minimal")
    payload["highlights"] = [{"title": "Missing description"}]
    with pytest.raises(jsonschema.ValidationError):
        _validator().validate(payload)


def test_executive_summary_rejects_unexpected_root_structure() -> None:
    payload = {**_fixture("minimal"), "x": 2.5, "color": "#00FF00"}
    with pytest.raises(jsonschema.ValidationError):
        _validator().validate(payload)


def test_executive_summary_re_lists_optional_shared_field_provenance() -> None:
    assert SCHEMA["properties"]["fieldProvenance"]["$ref"] == (
        "../base.schema.json#/properties/fieldProvenance"
    )
    payload = _fixture("minimal")
    assert payload["fieldProvenance"]
    _validator().validate(payload)
    legacy_compatible = copy.deepcopy(payload)
    del legacy_compatible["fieldProvenance"]
    _validator().validate(legacy_compatible)
