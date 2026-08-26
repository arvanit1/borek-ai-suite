"""ES-5 — KnowledgeModel schema contract."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "knowledge_model.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "fixtures" / "knowledge_model.minimal.json"

REQUIRED_BUCKETS = {
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
}


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_minimal_fixture_validates(schema: dict, fixture: dict) -> None:
    jsonschema.validate(instance=fixture, schema=schema)


def test_schema_requires_extraction_buckets(schema: dict) -> None:
    required = set(schema["required"])
    assert REQUIRED_BUCKETS <= required


def test_missing_facts_fails(schema: dict, fixture: dict) -> None:
    payload = dict(fixture)
    del payload["facts"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_entry_without_source_refs_fails(schema: dict, fixture: dict) -> None:
    payload = json.loads(json.dumps(fixture))
    payload["facts"][0] = {"statement": "Invented without a source"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_entry_without_origin_fails(schema: dict, fixture: dict) -> None:
    payload = json.loads(json.dumps(fixture))
    payload["facts"][0] = {
        "statement": payload["facts"][0]["statement"],
        "source_refs": payload["facts"][0]["source_refs"],
        "confidence": "high",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_invalid_excerpt_pointer_fails(schema: dict, fixture: dict) -> None:
    payload = json.loads(json.dumps(fixture))
    payload["facts"][0]["source_refs"][0]["excerpt_pointer"] = "paragraph-2"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)
