"""AT-2: PresentationPlan schema contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from packages.contracts.validators import validate_presentation_plan_business_rules

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "presentation_plan.schema.json"
FIXTURE_PATH = CONTRACTS_DIR / "fixtures" / "presentation_plan.minimal.json"
LAYOUT_REGISTRY_PATH = CONTRACTS_DIR / "layout_registry.json"

MVP_LAYOUT_IDS = [
    "COVER_01",
    "EXECUTIVE_SUMMARY_01",
    "CONTEXT_01",
    "PROBLEM_SOLUTION_01",
    "SCOPE_01",
    "REQUIREMENTS_MATRIX_01",
    "PROCESS_FLOW_01",
    "TIMELINE_01",
    "MILESTONES_01",
    "TEAM_FTE_01",
    "ARCHITECTURE_01",
    "COMPLIANCE_01",
    "SUCCESS_METRICS_01",
    "OPEN_QUESTIONS_01",
    "NEXT_STEPS_01",
]

PLANNED_SLIDE_REQUIRED_FIELDS = {"order", "purpose", "layoutId", "frameworkReferences"}


@pytest.fixture(scope="module")
def presentation_plan_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def minimal_presentation_plan() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.is_file()


def test_schema_requires_at2_fields(presentation_plan_schema: dict) -> None:
    planned_slide = presentation_plan_schema["$defs"]["PlannedSlide"]
    assert PLANNED_SLIDE_REQUIRED_FIELDS <= set(planned_slide["required"])
    assert PLANNED_SLIDE_REQUIRED_FIELDS <= set(planned_slide["properties"].keys())


def test_minimal_fixture_validates(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    jsonschema.validate(instance=minimal_presentation_plan, schema=presentation_plan_schema)


def test_fixture_matches_technical_plan_example(minimal_presentation_plan: dict) -> None:
    assert minimal_presentation_plan["title"] == "Invoice 3-Way Match - Automation Proposal"
    slides = minimal_presentation_plan["slides"]
    assert [s["order"] for s in slides] == [1, 2, 3, 4, 5]
    assert slides[0]["layoutId"] == "COVER_01"
    assert slides[0]["frameworkReferences"] == ["opportunity"]
    assert slides[3]["layoutId"] == "PROCESS_FLOW_01"


def test_schema_rejects_unknown_layout_id(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    slides = [dict(s) for s in minimal_presentation_plan["slides"]]
    slides[0] = {**slides[0], "layoutId": "COOL_TIMELINE_BLUE_27"}
    invalid = {**minimal_presentation_plan, "slides": slides}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=presentation_plan_schema)


def test_schema_rejects_missing_framework_references(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    slides = [dict(s) for s in minimal_presentation_plan["slides"]]
    slides[0] = {**slides[0], "frameworkReferences": []}
    invalid = {**minimal_presentation_plan, "slides": slides}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=presentation_plan_schema)


def test_schema_rejects_invalid_framework_reference(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    slides = [dict(s) for s in minimal_presentation_plan["slides"]]
    slides[0] = {**slides[0], "frameworkReferences": ["chapter_99"]}
    invalid = {**minimal_presentation_plan, "slides": slides}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=presentation_plan_schema)


def test_schema_rejects_missing_purpose(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    slides = [dict(s) for s in minimal_presentation_plan["slides"]]
    del slides[0]["purpose"]
    invalid = {**minimal_presentation_plan, "slides": slides}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=presentation_plan_schema)


def test_schema_rejects_missing_order(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    slides = [dict(s) for s in minimal_presentation_plan["slides"]]
    del slides[0]["order"]
    invalid = {**minimal_presentation_plan, "slides": slides}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=presentation_plan_schema)


def test_schema_rejects_missing_layout_id(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    slides = [dict(s) for s in minimal_presentation_plan["slides"]]
    del slides[0]["layoutId"]
    invalid = {**minimal_presentation_plan, "slides": slides}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=presentation_plan_schema)


def test_at2_backlog_done_when_fields_are_required(presentation_plan_schema: dict) -> None:
    """Maps 1:1 to AT-2 done-when: order, purpose, layoutId, frameworkReferences per slide."""
    planned_slide = presentation_plan_schema["$defs"]["PlannedSlide"]
    assert planned_slide["required"] == ["order", "purpose", "layoutId", "frameworkReferences"]


def test_technical_plan_section12_example_validates_with_schema_version(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    """Section 12 example omits schema_version; canonical stored plans must include it (section 32)."""
    section12_shape = {
        "schema_version": "1.0",
        "title": "Invoice 3-Way Match - Automation Proposal",
        "slides": minimal_presentation_plan["slides"],
    }
    jsonschema.validate(instance=section12_shape, schema=presentation_plan_schema)


def test_presentation_plan_fixture_passes_business_rules() -> None:
    fixture_path = CONTRACTS_DIR / "fixtures" / "presentation_plan.minimal.json"
    plan = json.loads(fixture_path.read_text(encoding="utf-8"))
    validate_presentation_plan_business_rules(plan)


def test_layout_ids_align_with_layout_registry() -> None:
    registry = json.loads(LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry_ids = set(registry["layouts"].keys())
    assert set(MVP_LAYOUT_IDS) == registry_ids


def test_additive_fields_allowed_at_root(
    presentation_plan_schema: dict, minimal_presentation_plan: dict
) -> None:
    extended = {**minimal_presentation_plan, "planner_model": "gpt-4.1"}
    jsonschema.validate(instance=extended, schema=presentation_plan_schema)
