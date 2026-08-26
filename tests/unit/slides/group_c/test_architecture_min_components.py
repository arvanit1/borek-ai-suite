"""MS-13: ARCHITECTURE_01 requires at least two components, even without AT-7."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.business_rules import (
    MIN_ARCHITECTURE_COMPONENTS,
    ArchitectureMinComponentsError,
    validate_architecture_min_components,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "architecture_01.minimal.json"
)
METRICS_FIXTURE_PATH = (
    ROOT
    / "packages"
    / "contracts"
    / "fixtures"
    / "slide_spec"
    / "success_metrics_01.minimal.json"
)


def _architecture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_ms13_invoice_architecture_fixture_passes() -> None:
    payload = _architecture()
    before = copy.deepcopy(payload)
    validate_architecture_min_components(payload)
    assert payload == before
    assert len(payload["components"]) >= MIN_ARCHITECTURE_COMPONENTS


def test_ms13_exactly_two_components_passes() -> None:
    payload = _architecture()
    payload["components"] = payload["components"][:2]
    validate_architecture_min_components(payload)


@pytest.mark.parametrize("count", [0, 1])
def test_ms13_fewer_than_two_components_fails(count: int) -> None:
    payload = _architecture()
    payload["components"] = payload["components"][:count]
    with pytest.raises(ArchitectureMinComponentsError, match="at least 2 components"):
        validate_architecture_min_components(payload)


def test_ms13_missing_or_non_list_components_fails() -> None:
    payload = _architecture()
    del payload["components"]
    with pytest.raises(ArchitectureMinComponentsError, match="got 0"):
        validate_architecture_min_components(payload)

    payload = _architecture()
    payload["components"] = "not-a-list"
    with pytest.raises(ArchitectureMinComponentsError, match="got 0"):
        validate_architecture_min_components(payload)


def test_ms13_does_not_depend_on_constraint_yaml() -> None:
    """The business rule must fail even when AT-7 / MS-12 is never called."""
    payload = {
        "layoutId": "ARCHITECTURE_01",
        "title": "How It Is Built",
        "sourceChapterIds": ["6", "7"],
        "components": [{"number": 1, "title": "Only node", "description": "alone"}],
    }
    with pytest.raises(ArchitectureMinComponentsError):
        validate_architecture_min_components(payload)


def test_ms13_ignores_non_architecture_layouts() -> None:
    payload = json.loads(METRICS_FIXTURE_PATH.read_text(encoding="utf-8"))
    validate_architecture_min_components(payload)
