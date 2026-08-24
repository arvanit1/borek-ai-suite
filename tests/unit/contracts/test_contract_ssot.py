"""AT-1 / AT-2 single-source-of-truth and registry alignment tests."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from packages.contracts.validators import (
    ContractValidationError,
    chapter_specs_from_framework_schema,
    chapter_specs_from_registry,
    layout_ids_from_presentation_schema,
    layout_ids_from_registry,
    layout_ids_from_slide_spec_base_schema,
    validate_presentation_plan_business_rules,
)

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts"


@pytest.fixture(scope="module")
def chapter_registry() -> dict:
    return json.loads((CONTRACTS_DIR / "chapter_registry.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def layout_registry() -> dict:
    return json.loads((CONTRACTS_DIR / "layout_registry.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def framework_schema() -> dict:
    return json.loads((CONTRACTS_DIR / "framework_object.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def presentation_plan_schema() -> dict:
    return json.loads((CONTRACTS_DIR / "presentation_plan.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def slide_spec_base_schema() -> dict:
    return json.loads((CONTRACTS_DIR / "slide_spec" / "base.schema.json").read_text(encoding="utf-8"))


def test_chapter_registry_matches_framework_schema(
    chapter_registry: dict, framework_schema: dict
) -> None:
    assert chapter_specs_from_registry(chapter_registry) == chapter_specs_from_framework_schema(
        framework_schema
    )


def test_layout_registry_matches_presentation_plan_schema(
    layout_registry: dict, presentation_plan_schema: dict
) -> None:
    assert layout_ids_from_registry(layout_registry) == layout_ids_from_presentation_schema(
        presentation_plan_schema
    )


def test_layout_registry_matches_slide_spec_base_schema(
    layout_registry: dict, slide_spec_base_schema: dict
) -> None:
    assert layout_ids_from_registry(layout_registry) == layout_ids_from_slide_spec_base_schema(
        slide_spec_base_schema
    )


def test_slide_spec_base_layout_ids_match_presentation_plan(
    presentation_plan_schema: dict, slide_spec_base_schema: dict
) -> None:
    assert layout_ids_from_presentation_schema(presentation_plan_schema) == layout_ids_from_slide_spec_base_schema(
        slide_spec_base_schema
    )


def test_framework_schema_rejects_wrong_chapter_title(
    framework_schema: dict, chapter_registry: dict
) -> None:
    fixture_path = CONTRACTS_DIR / "fixtures" / "framework_object.minimal.json"
    obj = json.loads(fixture_path.read_text(encoding="utf-8"))
    obj["chapters"][1]["title"] = "Wrong title"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=obj, schema=framework_schema)


def test_presentation_plan_rejects_duplicate_order() -> None:
    fixture_path = CONTRACTS_DIR / "fixtures" / "presentation_plan.minimal.json"
    plan = json.loads(fixture_path.read_text(encoding="utf-8"))
    plan["slides"].append(dict(plan["slides"][0]))
    with pytest.raises(ContractValidationError):
        validate_presentation_plan_business_rules(plan)


def test_presentation_plan_accepts_contiguous_orders() -> None:
    fixture_path = CONTRACTS_DIR / "fixtures" / "presentation_plan.minimal.json"
    plan = json.loads(fixture_path.read_text(encoding="utf-8"))
    validate_presentation_plan_business_rules(plan)
