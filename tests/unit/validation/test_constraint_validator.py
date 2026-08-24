"""AT-7: generic constraint validator tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.validation.constraint_validator import (
    ConstraintValidationError,
    LayoutConstraintRegistry,
    validate_against_constraints,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
VALIDATOR_SOURCE = ROOT / "apps" / "api" / "services" / "validation" / "constraint_validator.py"
LAYOUT_REGISTRY = json.loads((CONTRACTS_DIR / "layout_registry.json").read_text(encoding="utf-8"))

# Mirrors technical plan section 15 TIMELINE_01_RULES — config data only, not Python branches.
TIMELINE_01_CONSTRAINT_CONFIG = {
    "properties": {
        "title": {"required": True, "type": "string", "max_length": 120},
        "phases": {
            "required": True,
            "type": "array",
            "min_items": 2,
            "max_items": 8,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"required": True, "type": "string", "max_length": 28},
                    "description": {"type": "string", "max_length": 75},
                },
            },
        },
    }
}

ARCHITECTURE_01_CONSTRAINT_CONFIG = {
    "properties": {
        "title": {"required": True, "type": "string", "max_length": 120},
        "components": {
            "required": True,
            "type": "array",
            "min_items": 2,
            "max_items": 8,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"required": True, "type": "string", "max_length": 40},
                    "description": {"type": "string", "max_length": 100},
                },
            },
        },
    }
}


@pytest.fixture
def architecture_slide_spec() -> dict:
    return json.loads(
        (CONTRACTS_DIR / "fixtures" / "slide_spec" / "architecture_01.minimal.json").read_text(
            encoding="utf-8"
        )
    )


def test_at7_valid_architecture_fixture_passes_constraints(architecture_slide_spec: dict) -> None:
    validate_against_constraints(architecture_slide_spec, ARCHITECTURE_01_CONSTRAINT_CONFIG)


def test_at7_missing_required_field_fails() -> None:
    payload = {
        "layoutId": "FAKE_01",
        "phases": [{"name": "A", "description": "ok"}, {"name": "B", "description": "ok"}],
    }
    with pytest.raises(ConstraintValidationError, match="Missing required field: title"):
        validate_against_constraints(payload, TIMELINE_01_CONSTRAINT_CONFIG)


def test_at7_wrong_type_fails() -> None:
    payload = {
        "title": "Timeline",
        "phases": "not-an-array",
    }
    with pytest.raises(ConstraintValidationError, match="Expected array at phases"):
        validate_against_constraints(payload, TIMELINE_01_CONSTRAINT_CONFIG)


def test_at7_array_min_items_fails() -> None:
    payload = {
        "title": "Timeline",
        "phases": [{"name": "Only one", "description": "x"}],
    }
    with pytest.raises(ConstraintValidationError, match="item count 1 is below minimum 2"):
        validate_against_constraints(payload, TIMELINE_01_CONSTRAINT_CONFIG)


def test_at7_array_max_items_fails() -> None:
    payload = {
        "title": "Timeline",
        "phases": [{"name": f"P{i}", "description": "d"} for i in range(9)],
    }
    with pytest.raises(ConstraintValidationError, match="item count 9 exceeds maximum 8"):
        validate_against_constraints(payload, TIMELINE_01_CONSTRAINT_CONFIG)


def test_at7_string_max_length_fails() -> None:
    payload = {
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "B", "description": "ok"},
        ],
    }
    with pytest.raises(ConstraintValidationError, match=r"phases\[0\]\.name length 29 exceeds maximum 28"):
        validate_against_constraints(payload, TIMELINE_01_CONSTRAINT_CONFIG)


def test_at7_registry_validates_by_layout_id(architecture_slide_spec: dict) -> None:
    registry = LayoutConstraintRegistry()
    registry.register("ARCHITECTURE_01", ARCHITECTURE_01_CONSTRAINT_CONFIG)
    registry.validate_slide_spec(architecture_slide_spec)


def test_at7_registry_unknown_layout_id_fails(architecture_slide_spec: dict) -> None:
    registry = LayoutConstraintRegistry()
    with pytest.raises(ConstraintValidationError, match="No constraint config registered"):
        registry.validate_slide_spec(architecture_slide_spec)


def test_at7_validator_has_no_layout_specific_branches() -> None:
    """Maps to AT-7 done-when: no layout-specific code inside the validator."""
    source = VALIDATOR_SOURCE.read_text(encoding="utf-8")
    for layout_id in LAYOUT_REGISTRY["layouts"]:
        assert layout_id not in source


def test_at7_fake_layout_works_via_config_only() -> None:
    """Any layout validates through config registration — no code changes required."""
    config = {
        "properties": {
            "widgets": {
                "required": True,
                "type": "array",
                "min_items": 1,
                "max_items": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"required": True, "type": "string", "max_length": 10},
                    },
                },
            }
        }
    }
    payload = {"layoutId": "FAKE_01", "widgets": [{"label": "ok"}]}
    registry = LayoutConstraintRegistry()
    registry.register("FAKE_01", config)
    registry.validate_slide_spec(payload)
