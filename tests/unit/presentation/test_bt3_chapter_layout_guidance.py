"""BT-3: canonical chapter-to-layout planner guidance coverage."""

from __future__ import annotations

import copy
import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest

from services.presentation import chapter_layout_guidance, registry_validation
from services.presentation.chapter_layout_guidance import (
    CHAPTER_LAYOUT_MAP_PATH,
    ChapterLayoutGuidanceError,
    load_chapter_layout_guidance,
)
from services.presentation.planner import (
    PROMPT_PATH,
    PresentationPlanValidationError,
    plan_presentation,
)
from services.presentation.registry_validation import registered_layout_ids

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE = (
    ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
)
PLAN_FIXTURE = (
    ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"
)
PLANNER_PATH = ROOT / "apps" / "api" / "services" / "presentation" / "planner.py"
GUIDANCE_PATH = (
    ROOT
    / "apps"
    / "api"
    / "services"
    / "presentation"
    / "chapter_layout_guidance.py"
)


class RecordingPlanner:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete_planning(self, **request: Any) -> dict[str, Any]:
        self.calls.append(copy.deepcopy(request))
        return copy.deepcopy(self.response)


@pytest.fixture
def confirmed_framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def valid_plan() -> dict[str, Any]:
    return json.loads(PLAN_FIXTURE.read_text(encoding="utf-8"))


def _mapping_for(*chapters: str) -> dict[str, Any]:
    matches = [
        mapping
        for mapping in load_chapter_layout_guidance()["mappings"]
        if mapping["chapters"] == list(chapters)
    ]
    assert len(matches) == 1
    return matches[0]


def test_canonical_map_is_runtime_source_and_preserves_semantics() -> None:
    raw = json.loads(CHAPTER_LAYOUT_MAP_PATH.read_text(encoding="utf-8"))
    guidance = load_chapter_layout_guidance()

    assert CHAPTER_LAYOUT_MAP_PATH == (
        ROOT / "packages" / "contracts" / "chapter_layout_map.json"
    )
    assert guidance == raw
    assert "guidance only" in guidance["description"].lower()
    assert _mapping_for("1")["layoutIds"] == [
        "COVER_01",
        "EXECUTIVE_SUMMARY_01",
        "CONTEXT_01",
    ]
    assert _mapping_for("2", "4")["layoutIds"] == [
        "PROBLEM_SOLUTION_01",
        "PROCESS_FLOW_01",
    ]
    success_metrics = _mapping_for("3", "9")
    assert success_metrics["layoutIds"] == ["SUCCESS_METRICS_01"]
    assert success_metrics["excludeMonetaryFields"] is True

    mapped_layouts = {
        layout_id
        for mapping in guidance["mappings"]
        for layout_id in mapping["layoutIds"]
    }
    assert mapped_layouts <= registered_layout_ids()


def test_guidance_reaches_same_single_call_without_mutating_framework(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    snapshot = copy.deepcopy(confirmed_framework)
    planner = RecordingPlanner(valid_plan)

    result = plan_presentation(confirmed_framework, planner=planner)

    assert result.model_dump(mode="json") == valid_plan
    assert len(planner.calls) == 1
    call = planner.calls[0]
    assert call["retry_count"] == 0
    assert call["planning_input"]["chapterLayoutGuidance"] == json.loads(
        CHAPTER_LAYOUT_MAP_PATH.read_text(encoding="utf-8")
    )
    assert call["planning_input"]["frameworkObject"]["status"] == "confirmed"
    assert confirmed_framework == snapshot


def test_runtime_mapping_drift_is_reflected_without_a_hardcoded_copy(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drifted = {
        "schema_version": "1.0",
        "description": "Planner guidance only.",
        "mappings": [
            {"chapters": ["1"], "layoutIds": ["CONTEXT_01"]},
            {
                "chapters": ["3", "9"],
                "layoutIds": ["SUCCESS_METRICS_01"],
                "excludeMonetaryFields": True,
            },
        ],
    }
    runtime_map = tmp_path / "chapter_layout_map.json"
    runtime_map.write_text(json.dumps(drifted), encoding="utf-8")
    monkeypatch.setattr(
        chapter_layout_guidance, "CHAPTER_LAYOUT_MAP_PATH", runtime_map
    )
    planner = RecordingPlanner(valid_plan)

    plan_presentation(confirmed_framework, planner=planner)

    assert len(planner.calls) == 1
    assert planner.calls[0]["planning_input"]["chapterLayoutGuidance"] == drifted


@pytest.mark.parametrize(
    "contents,match",
    [
        ("not-json", "Malformed chapter-layout guidance"),
        ('{"schema_version": "1.0", "mappings": []}', "description"),
        (
            '{"schema_version":"1.0","description":"guidance",'
            '"mappings":[{"chapters":["1"],"layoutIds":[]}]}',
            "layoutIds",
        ),
        (
            '{"schema_version":"1.0","description":"guidance",'
            '"mappings":[{"chapters":["3","9"],'
            '"layoutIds":["SUCCESS_METRICS_01"],'
            '"excludeMonetaryFields":"yes"}]}',
            "excludeMonetaryFields",
        ),
    ],
)
def test_malformed_mapping_fails_before_planning(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contents: str,
    match: str,
) -> None:
    runtime_map = tmp_path / "chapter_layout_map.json"
    runtime_map.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(
        chapter_layout_guidance, "CHAPTER_LAYOUT_MAP_PATH", runtime_map
    )
    planner = RecordingPlanner(valid_plan)

    with pytest.raises(ChapterLayoutGuidanceError, match=match):
        plan_presentation(confirmed_framework, planner=planner)

    assert planner.calls == []


def test_unavailable_mapping_fails_before_planning(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "missing-chapter-layout-map.json"
    monkeypatch.setattr(chapter_layout_guidance, "CHAPTER_LAYOUT_MAP_PATH", missing)
    planner = RecordingPlanner(valid_plan)

    with pytest.raises(ChapterLayoutGuidanceError, match="Unable to load"):
        plan_presentation(confirmed_framework, planner=planner)

    assert planner.calls == []


def test_mapping_is_guidance_not_a_hard_layout_override(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    planner_choice = copy.deepcopy(valid_plan)
    planner_choice["slides"][0]["frameworkReferences"] = ["chapter_2"]
    planner = RecordingPlanner(planner_choice)

    result = plan_presentation(confirmed_framework, planner=planner)

    assert result.slides[0].layoutId.value == "COVER_01"
    assert result.model_dump(mode="json")["slides"][0]["frameworkReferences"] == [
        "chapter_2"
    ]
    assert len(planner.calls) == 1


def test_bt2_registry_validation_still_rejects_runtime_drift_once(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = json.loads(
        registry_validation.LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8")
    )
    del registry["layouts"]["CONTEXT_01"]
    runtime_registry = tmp_path / "layout_registry.json"
    runtime_registry.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(
        registry_validation, "LAYOUT_REGISTRY_PATH", runtime_registry
    )
    planner = RecordingPlanner(valid_plan)

    with pytest.raises(PresentationPlanValidationError, match="CONTEXT_01"):
        plan_presentation(confirmed_framework, planner=planner)

    assert len(planner.calls) == 1


def test_prompt_declares_guidance_grounding_and_commercial_rules() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    lowered = prompt.lower()

    assert PROMPT_PATH.name == "presentation_planner_v2.txt"
    assert "guidance, not a mandatory" in lowered
    assert "do not force every mapped layout" in lowered
    assert "omit unnecessary, thin" in lowered
    assert "frameworkreferences" in lowered
    assert "excludemonetaryfields=true" in lowered
    assert "pricing" in lowered and "currency" in lowered and "commercial" in lowered
    assert "coordinates" in lowered and "geometry" in lowered


def test_production_contains_no_hardcoded_mapping_or_extra_stage_b_inputs() -> None:
    production = "\n".join(
        [
            PLANNER_PATH.read_text(encoding="utf-8"),
            GUIDANCE_PATH.read_text(encoding="utf-8"),
            PROMPT_PATH.read_text(encoding="utf-8"),
        ]
    )
    parameters = inspect.signature(plan_presentation).parameters

    hardcoded_layout_ids = {
        layout_id for layout_id in registered_layout_ids() if layout_id in production
    }
    assert hardcoded_layout_ids == {"PROCESS_FLOW_01"}
    assert list(parameters) == ["confirmed_framework", "planner"]
    assert "transcript" not in parameters
    assert "claude" not in parameters


def test_valid_flow_requires_no_api_key_or_network(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    planner = RecordingPlanner(valid_plan)

    result = plan_presentation(confirmed_framework, planner=planner)

    assert result.model_dump(mode="json") == valid_plan
    assert len(planner.calls) == 1
    assert "OPENAI_API_KEY" not in os.environ
    assert "ANTHROPIC_API_KEY" not in os.environ
