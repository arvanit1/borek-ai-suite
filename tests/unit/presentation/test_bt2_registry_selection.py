"""BT-2: canonical registry-only PresentationPlan layout selection."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from services.presentation import registry_validation
from services.presentation.planner import (
    PresentationPlanValidationError,
    plan_presentation,
)
from services.presentation.registry_validation import (
    LAYOUT_REGISTRY_PATH,
    UnregisteredLayoutError,
    registered_layout_ids,
    validate_registry_layout_selection,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
PLAN_FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"
REGISTRY_VALIDATION_PATH = (
    ROOT
    / "apps"
    / "api"
    / "services"
    / "presentation"
    / "registry_validation.py"
)


class CountingPlanner:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def complete_planning(self, **_: Any) -> dict[str, Any]:
        self.calls += 1
        return copy.deepcopy(self.response)


@pytest.fixture
def confirmed_framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def valid_plan() -> dict[str, Any]:
    return json.loads(PLAN_FIXTURE.read_text(encoding="utf-8"))


def test_canonical_registry_is_the_runtime_source_of_truth() -> None:
    registry = json.loads(LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8"))

    assert LAYOUT_REGISTRY_PATH == ROOT / "packages" / "contracts" / "layout_registry.json"
    assert registered_layout_ids() == frozenset(registry["layouts"])


def test_every_registered_layout_is_accepted() -> None:
    plan = {
        "slides": [
            {"layoutId": layout_id}
            for layout_id in sorted(registered_layout_ids())
        ]
    }

    validate_registry_layout_selection(plan)


def test_unknown_layout_is_rejected_with_offending_id() -> None:
    unknown = "UNKNOWN_LAYOUT_99"

    with pytest.raises(UnregisteredLayoutError, match=unknown):
        validate_registry_layout_selection({"slides": [{"layoutId": unknown}]})


def test_one_unknown_layout_rejects_whole_plan_without_retry_or_mutation(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    invalid = copy.deepcopy(valid_plan)
    invalid["slides"][2]["layoutId"] = "UNREGISTERED_MIDDLE_01"
    framework_snapshot = copy.deepcopy(confirmed_framework)
    plan_snapshot = copy.deepcopy(invalid)
    planner = CountingPlanner(invalid)

    with pytest.raises(PresentationPlanValidationError, match="UNREGISTERED_MIDDLE_01"):
        plan_presentation(confirmed_framework, planner=planner)

    assert planner.calls == 1
    assert confirmed_framework == framework_snapshot
    assert invalid == plan_snapshot


def test_runtime_registry_drift_is_rejected_after_schema_validation(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = json.loads(LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8"))
    del registry["layouts"]["CONTEXT_01"]
    runtime_registry = tmp_path / "layout_registry.json"
    runtime_registry.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(registry_validation, "LAYOUT_REGISTRY_PATH", runtime_registry)
    planner = CountingPlanner(valid_plan)

    with pytest.raises(PresentationPlanValidationError, match="CONTEXT_01"):
        plan_presentation(confirmed_framework, planner=planner)

    assert planner.calls == 1


def test_valid_bt1_flow_remains_one_call_and_needs_no_api_key(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    planner = CountingPlanner(valid_plan)

    result = plan_presentation(confirmed_framework, planner=planner)

    assert result.model_dump(mode="json") == valid_plan
    assert planner.calls == 1
    assert "OPENAI_API_KEY" not in os.environ
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_bt2_registry_validation_remains_independent_of_bt3_guidance() -> None:
    source = REGISTRY_VALIDATION_PATH.read_text(encoding="utf-8")

    assert "layout_registry.json" in source
    assert "chapter_layout" not in source
