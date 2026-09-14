"""JJ-32 — FollowupExtraction schema contract."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "followup_extraction.schema.json"
FIXTURE_DIR = CONTRACTS_DIR / "fixtures" / "followup_extraction"
CASES_PATH = FIXTURE_DIR / "cases.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workshop() -> dict:
    return json.loads((FIXTURE_DIR / "workshop_clear.json").read_text(encoding="utf-8"))


def test_schema_is_frozen_object_with_no_extra_properties(schema: dict) -> None:
    assert schema["additionalProperties"] is False
    required = set(schema["required"])
    assert {
        "meeting_topic",
        "meeting_date",
        "project_name",
        "participants",
        "key_points",
        "decisions",
        "action_items",
        "open_questions",
        "next_meeting",
        "confidence",
        "review_flags",
        "schema_version",
        "prompt_version",
    } <= required
    assert schema["properties"]["key_points"]["maxItems"] == 3
    assert schema["properties"]["action_items"]["maxItems"] == 5
    assert schema["properties"]["project_name"]["type"] == ["string", "null"]


def test_every_frozen_fixture_validates(schema: dict) -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    for name in cases:
        payload = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
        jsonschema.validate(instance=payload, schema=schema)
        assert payload["schema_version"] == "1.0"
        assert payload["prompt_version"] == "followup-extraction:v1"
        assert payload["project_name"] is None
        assert len(payload["key_points"]) <= 3
        assert len(payload["action_items"]) <= 5


def test_missing_action_items_fails(schema: dict, workshop: dict) -> None:
    payload = deepcopy(workshop)
    del payload["action_items"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_fourth_key_point_fails(schema: dict, workshop: dict) -> None:
    payload = deepcopy(workshop)
    payload["key_points"].append("A fourth outcome is not allowed")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_sixth_action_fails(schema: dict, workshop: dict) -> None:
    payload = deepcopy(workshop)
    extra = deepcopy(payload["action_items"][0])
    extra["action"] = "Write the cutover checklist"
    payload["action_items"].extend([deepcopy(extra), deepcopy(extra), deepcopy(extra), extra])
    assert len(payload["action_items"]) == 6
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_null_action_owner_fails(schema: dict, workshop: dict) -> None:
    payload = deepcopy(workshop)
    payload["action_items"][0]["owner"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_guessed_due_date_without_tbd_or_ddmmyyyy_fails(schema: dict, workshop: dict) -> None:
    payload = deepcopy(workshop)
    payload["action_items"][0]["due"] = "next week"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)


def test_unknown_root_field_fails(schema: dict, workshop: dict) -> None:
    payload = deepcopy(workshop)
    payload["email_body"] = "invented"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=payload, schema=schema)
