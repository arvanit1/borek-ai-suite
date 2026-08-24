"""AT-6: schema_version + additive field consumer behavior."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.contracts.schema_consumer import (
    SchemaVersionMismatchError,
    consume_framework_object,
    consume_presentation_plan,
    consume_slide_spec_base,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = ROOT / "packages" / "contracts" / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def run_pydantic_codegen() -> None:
    subprocess.run([sys.executable, "scripts/generate_pydantic.py"], cwd=ROOT, check=True)


@pytest.fixture
def framework_object_payload() -> dict:
    return json.loads((FIXTURES_DIR / "framework_object.minimal.json").read_text(encoding="utf-8"))


@pytest.fixture
def presentation_plan_payload() -> dict:
    return json.loads((FIXTURES_DIR / "presentation_plan.minimal.json").read_text(encoding="utf-8"))


@pytest.fixture
def slide_spec_payload() -> dict:
    return json.loads(
        (FIXTURES_DIR / "slide_spec" / "architecture_01.minimal.json").read_text(encoding="utf-8")
    )


def test_at6_framework_object_fixture_consumes(framework_object_payload: dict) -> None:
    obj = consume_framework_object(framework_object_payload)
    assert obj.schema_version == "1.0"
    assert len(obj.chapters) == 14


def test_at6_unrecognized_additive_field_is_ignored_for_framework_object(
    framework_object_payload: dict,
) -> None:
    payload = {**framework_object_payload, "future_field": "from-schema-v1.1"}
    obj = consume_framework_object(payload)
    dumped = obj.model_dump()
    assert "future_field" not in dumped
    assert "future_field" not in (obj.model_extra or {})


def test_at6_unrecognized_additive_field_is_ignored_for_presentation_plan(
    presentation_plan_payload: dict,
) -> None:
    payload = {**presentation_plan_payload, "future_metadata": {"owner": "ops"}}
    plan = consume_presentation_plan(payload)
    dumped = plan.model_dump()
    assert "future_metadata" not in dumped
    assert "future_metadata" not in (plan.model_extra or {})


def test_at6_slide_spec_preserves_layout_specific_fields(slide_spec_payload: dict) -> None:
    payload = {**slide_spec_payload, "future_field": "ignored-by-business-logic"}
    spec = consume_slide_spec_base(payload)
    assert spec.model_extra is not None
    assert "components" in spec.model_extra
    assert spec.model_extra["future_field"] == "ignored-by-business-logic"


def test_at6_missing_required_field_raises_version_mismatch(framework_object_payload: dict) -> None:
    payload = copy.deepcopy(framework_object_payload)
    del payload["title"]
    with pytest.raises(SchemaVersionMismatchError, match="schema_version 1.0 mismatch: missing required field"):
        consume_framework_object(payload)


def test_at6_unsupported_schema_version_raises_version_mismatch(framework_object_payload: dict) -> None:
    payload = {**framework_object_payload, "schema_version": "2.0"}
    with pytest.raises(SchemaVersionMismatchError, match="schema_version mismatch: unsupported version '2.0'"):
        consume_framework_object(payload)


def test_at6_missing_schema_version_raises_version_mismatch(framework_object_payload: dict) -> None:
    payload = copy.deepcopy(framework_object_payload)
    del payload["schema_version"]
    with pytest.raises(SchemaVersionMismatchError, match="missing required field\\(s\\): schema_version"):
        consume_framework_object(payload)


def test_at6_version_mismatch_error_is_clear_for_presentation_plan(presentation_plan_payload: dict) -> None:
    payload = copy.deepcopy(presentation_plan_payload)
    del payload["slides"]
    with pytest.raises(SchemaVersionMismatchError) as exc_info:
        consume_presentation_plan(payload)
    message = str(exc_info.value)
    assert "PresentationPlan" in message
    assert "schema_version" in message
    assert "mismatch" in message
    assert "slides" in message


def test_at6_non_object_payload_raises_version_mismatch() -> None:
    with pytest.raises(SchemaVersionMismatchError, match="expected object payload"):
        consume_framework_object(["not", "an", "object"])


def test_at6_invalid_field_values_still_fail_after_additive_strip(framework_object_payload: dict) -> None:
    payload = {**framework_object_payload, "future_field": "ok", "status": "approved"}
    with pytest.raises(ValidationError):
        consume_framework_object(payload)
