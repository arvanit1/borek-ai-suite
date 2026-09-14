"""BT-1/BT-3: duplicate layout retry context and chapter-split repair."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from services.presentation.planner import (
    PresentationPlanValidationError,
    duplicate_layout_ids_from_plan,
    plan_presentation,
    repair_chapter_split_duplicate_layouts,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
PLAN_FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"


@pytest.fixture
def confirmed_framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def valid_plan() -> dict[str, Any]:
    return json.loads(PLAN_FIXTURE.read_text(encoding="utf-8"))


def _duplicate_chapter_split_plan() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "title": "Split chapter duplicates",
        "slides": [
            {
                "order": 1,
                "purpose": "cover",
                "layoutId": "COVER_01",
                "frameworkReferences": ["opportunity"],
            },
            {
                "order": 2,
                "purpose": "problem for chapter 2",
                "layoutId": "PROBLEM_SOLUTION_01",
                "frameworkReferences": ["chapter_2"],
            },
            {
                "order": 3,
                "purpose": "process for chapter 2",
                "layoutId": "PROCESS_FLOW_01",
                "frameworkReferences": ["chapter_2"],
            },
            {
                "order": 4,
                "purpose": "problem for chapter 4",
                "layoutId": "PROBLEM_SOLUTION_01",
                "frameworkReferences": ["chapter_4"],
            },
            {
                "order": 5,
                "purpose": "process for chapter 4",
                "layoutId": "PROCESS_FLOW_01",
                "frameworkReferences": ["chapter_4"],
            },
        ],
    }


class SequentialPlanner:
    def __init__(self, *responses: dict[str, Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete_planning(
        self,
        *,
        planning_input: dict[str, Any] | None = None,
        prompt_version: str = "v1",
        retry_count: int = 0,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "planning_input": copy.deepcopy(planning_input),
                "prompt_version": prompt_version,
                "retry_count": retry_count,
            }
        )
        index = min(retry_count, len(self.responses) - 1)
        return copy.deepcopy(self.responses[index])


class RepeatingPlanner:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete_planning(
        self,
        *,
        planning_input: dict[str, Any] | None = None,
        prompt_version: str = "v1",
        retry_count: int = 0,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "planning_input": copy.deepcopy(planning_input),
                "retry_count": retry_count,
            }
        )
        return copy.deepcopy(self.response)


def test_retry_receives_duplicate_layout_ids(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    invalid = copy.deepcopy(valid_plan)
    duplicate = copy.deepcopy(invalid["slides"][1])
    duplicate["order"] = len(invalid["slides"]) + 1
    duplicate["purpose"] = "duplicate context"
    invalid["slides"].append(duplicate)
    planner = SequentialPlanner(invalid, valid_plan)

    result = plan_presentation(confirmed_framework, planner=planner)

    assert result.model_dump(mode="json") == valid_plan
    assert len(planner.calls) == 2
    retry_input = planner.calls[1]["planning_input"]
    assert retry_input is not None
    assert retry_input["retryValidationErrors"]["duplicateLayoutIds"] == [
        "CONTEXT_01",
    ]
    assert retry_input["forbiddenDuplicateLayoutIds"] == ["CONTEXT_01"]
    assert retry_input["previousInvalidPlan"] == invalid
    assert retry_input["retryValidationErrors"]["duplicateLayoutIds"] == ["CONTEXT_01"]


def test_repeated_invalid_response_respects_retry_limit(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    invalid = copy.deepcopy(valid_plan)
    duplicate = copy.deepcopy(invalid["slides"][1])
    duplicate["order"] = len(invalid["slides"]) + 1
    duplicate["purpose"] = "duplicate context"
    invalid["slides"].append(duplicate)
    planner = RepeatingPlanner(invalid)

    with pytest.raises(
        PresentationPlanValidationError,
        match="CONTEXT_01",
    ):
        plan_presentation(confirmed_framework, planner=planner)

    assert len(planner.calls) == 3
    assert [call["retry_count"] for call in planner.calls] == [0, 1, 2]
    retry_input = planner.calls[2]["planning_input"]
    assert retry_input["retryValidationErrors"]["duplicateLayoutIds"] == [
        "CONTEXT_01",
    ]


def test_chapter_two_and_four_mapping_produces_one_layout_each(
    confirmed_framework: dict[str, Any],
) -> None:
    invalid = _duplicate_chapter_split_plan()
    planner = RepeatingPlanner(invalid)

    result = plan_presentation(confirmed_framework, planner=planner)

    layout_ids = [slide.layoutId.value for slide in result.slides]
    assert layout_ids.count("PROBLEM_SOLUTION_01") == 1
    assert layout_ids.count("PROCESS_FLOW_01") == 1
    problem = next(
        slide for slide in result.slides if slide.layoutId.value == "PROBLEM_SOLUTION_01"
    )
    process = next(
        slide for slide in result.slides if slide.layoutId.value == "PROCESS_FLOW_01"
    )
    dumped = result.model_dump(mode="json")
    problem_refs = set(
        next(
            slide["frameworkReferences"]
            for slide in dumped["slides"]
            if slide["layoutId"] == "PROBLEM_SOLUTION_01"
        )
    )
    process_refs = set(
        next(
            slide["frameworkReferences"]
            for slide in dumped["slides"]
            if slide["layoutId"] == "PROCESS_FLOW_01"
        )
    )
    assert problem_refs == {"chapter_2", "chapter_4"}
    assert process_refs == {"chapter_2", "chapter_4"}
    assert len(planner.calls) == 1


def test_valid_unique_layout_plan_is_unchanged(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    planner = RepeatingPlanner(valid_plan)

    result = plan_presentation(confirmed_framework, planner=planner)

    assert result.model_dump(mode="json") == valid_plan
    assert len(planner.calls) == 1
    assert "retryValidationErrors" not in planner.calls[0]["planning_input"]


def test_unrelated_layout_selection_still_validates(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    custom = copy.deepcopy(valid_plan)
    custom["slides"] = [
        custom["slides"][0],
        {
            "order": 2,
            "purpose": "executive summary",
            "layoutId": "EXECUTIVE_SUMMARY_01",
            "frameworkReferences": ["chapter_1"],
        },
        custom["slides"][2],
    ]
    for order, slide in enumerate(custom["slides"], start=1):
        slide["order"] = order

    result = plan_presentation(confirmed_framework, planner=RepeatingPlanner(custom))

    assert [slide.layoutId.value for slide in result.slides] == [
        "COVER_01",
        "EXECUTIVE_SUMMARY_01",
        "SCOPE_01",
    ]


def test_duplicate_merge_preserves_chapter_coverage() -> None:
    invalid = _duplicate_chapter_split_plan()
    repaired = repair_chapter_split_duplicate_layouts(invalid)

    assert repaired is not None
    assert duplicate_layout_ids_from_plan(repaired) == []
    problem = next(
        slide for slide in repaired["slides"] if slide["layoutId"] == "PROBLEM_SOLUTION_01"
    )
    process = next(
        slide for slide in repaired["slides"] if slide["layoutId"] == "PROCESS_FLOW_01"
    )
    assert set(problem["frameworkReferences"]) == {"chapter_2", "chapter_4"}
    assert set(process["frameworkReferences"]) == {"chapter_2", "chapter_4"}
