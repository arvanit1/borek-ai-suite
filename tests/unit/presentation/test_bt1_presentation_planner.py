"""BT-1: one-call Presentation Planner coverage."""

from __future__ import annotations

import copy
import inspect
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from llm.client import LlmClient, LlmUsageResult
from services.observability.llm_logger import LlmStage, get_llm_call_logs, reset_llm_call_logs
from services.presentation import planner as planner_module
from services.presentation.planner import (
    FrameworkNotConfirmedError,
    PROMPT_PATH,
    PROMPT_VERSION,
    PresentationPlanValidationError,
    PresentationPlanningCallError,
    plan_presentation,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
PLAN_FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"


class MockPlanner:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete_planning(
        self,
        *,
        planning_input: dict[str, Any] | None = None,
        prompt_version: str = "v1",
        retry_count: int = 0,
    ) -> Any:
        self.calls.append(
            {
                "planning_input": copy.deepcopy(planning_input),
                "prompt_version": prompt_version,
                "retry_count": retry_count,
            }
        )
        return copy.deepcopy(self.response)


@pytest.fixture
def confirmed_framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def valid_plan() -> dict[str, Any]:
    return json.loads(PLAN_FIXTURE.read_text(encoding="utf-8"))


def test_confirmed_framework_produces_one_validated_plan_with_preserved_fields(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    snapshot = copy.deepcopy(confirmed_framework)
    planner = MockPlanner(valid_plan)

    plan = plan_presentation(confirmed_framework, planner=planner)

    assert len(planner.calls) == 1
    assert plan.model_dump(mode="json") == valid_plan
    assert plan.title == valid_plan["title"]
    assert [slide.order for slide in plan.slides] == [1, 2, 3, 4, 5]
    assert [slide.purpose for slide in plan.slides] == [
        "cover",
        "context",
        "scope",
        "process_flow",
        "timeline",
    ]
    assert [slide.layoutId.value for slide in plan.slides] == [
        slide["layoutId"] for slide in valid_plan["slides"]
    ]
    assert plan.model_dump(mode="json")["slides"][0]["frameworkReferences"] == [
        "opportunity"
    ]
    assert confirmed_framework == snapshot

    request = planner.calls[0]["planning_input"]
    assert request is not None
    assert set(request) == {
        "instructions",
        "frameworkObject",
        "chapterLayoutGuidance",
        "targetSchema",
    }
    assert request["frameworkObject"]["status"] == "confirmed"
    assert request["targetSchema"]["title"] == "PresentationPlan"
    assert "EXECUTIVE_SUMMARY_01" not in request["targetSchema"]["$defs"]["LayoutId"]["enum"]
    assert "COVER_01" in request["targetSchema"]["$defs"]["LayoutId"]["enum"]
    assert planner.calls[0]["prompt_version"] == PROMPT_VERSION
    assert planner.calls[0]["retry_count"] == 0


def test_llm_client_passes_framework_request_once_through_at53_observability(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    reset_llm_call_logs()
    executor_calls: list[tuple[Any, ...]] = []

    def request_aware_executor(
        stage: LlmStage,
        operation: str,
        prompt_version: str,
        retry_count: int,
        request: dict[str, Any],
    ) -> LlmUsageResult:
        executor_calls.append((stage, operation, prompt_version, retry_count, request))
        return LlmUsageResult(payload=valid_plan, input_tokens=320, output_tokens=180)

    plan = plan_presentation(
        confirmed_framework,
        planner=LlmClient(executor=request_aware_executor),
    )

    assert plan.title == valid_plan["title"]
    assert len(executor_calls) == 1
    stage, operation, prompt_version, retry_count, request = executor_calls[0]
    assert stage is LlmStage.PLANNING
    assert operation == "presentation_planner"
    assert prompt_version == PROMPT_VERSION
    assert retry_count == 0
    assert request["frameworkObject"]["status"] == "confirmed"
    logs = get_llm_call_logs()
    assert len(logs) == 1
    assert logs[0].stage == LlmStage.PLANNING.value
    assert logs[0].input_tokens == 320
    assert logs[0].output_tokens == 180


def test_complete_planning_keeps_legacy_executor_compatible_without_input() -> None:
    calls = 0

    def legacy_executor(stage, operation, prompt_version, retry_count):
        nonlocal calls
        calls += 1
        return LlmUsageResult(payload={"ok": True}, input_tokens=1, output_tokens=1)

    result = LlmClient(executor=legacy_executor).complete_planning()

    assert result == {"ok": True}
    assert calls == 1


def test_planning_rejects_executor_that_cannot_receive_framework_input(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    def legacy_executor(stage, operation, prompt_version, retry_count):
        return LlmUsageResult(payload=valid_plan, input_tokens=1, output_tokens=1)

    with pytest.raises(PresentationPlanningCallError, match="must accept"):
        plan_presentation(
            confirmed_framework,
            planner=LlmClient(executor=legacy_executor),
        )


def test_unconfirmed_framework_never_enters_planning(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    draft = copy.deepcopy(confirmed_framework)
    draft["status"] = "draft"
    planner = MockPlanner(valid_plan)

    with pytest.raises(FrameworkNotConfirmedError, match="status='confirmed'"):
        plan_presentation(draft, planner=planner)

    assert planner.calls == []
    assert draft["status"] == "draft"


@pytest.mark.parametrize(
    "invalid_response",
    [
        ["not", "an", "object"],
        {"schema_version": "1.0", "slides": [{"order": 1}]},
        {"schema_version": "1.0", "title": "Missing slides"},
        {"schema_version": "1.0", "title": "Empty", "slides": []},
        {"schema_version": "1.0", "title": "Malformed", "slides": [{}]},
        {
            "schema_version": "1.0",
            "title": "Missing purpose",
            "slides": [
                {
                    "order": 1,
                    "layoutId": "COVER_01",
                    "frameworkReferences": ["opportunity"],
                }
            ],
        },
        {
            "schema_version": "1.0",
            "title": "Missing layout",
            "slides": [
                {
                    "order": 1,
                    "purpose": "cover",
                    "frameworkReferences": ["opportunity"],
                }
            ],
        },
        {
            "schema_version": "1.0",
            "title": "Missing references",
            "slides": [
                {"order": 1, "purpose": "cover", "layoutId": "COVER_01"}
            ],
        },
        {
            "schema_version": "1.0",
            "title": "Invalid order",
            "slides": [
                {
                    "order": 0,
                    "purpose": "cover",
                    "layoutId": "COVER_01",
                    "frameworkReferences": ["opportunity"],
                }
            ],
        },
    ],
)
def test_invalid_planner_output_is_rejected_without_repair(
    confirmed_framework: dict[str, Any], invalid_response: Any
) -> None:
    planner = MockPlanner(invalid_response)

    with pytest.raises(PresentationPlanValidationError, match="Invalid PresentationPlan"):
        plan_presentation(confirmed_framework, planner=planner)

    assert len(planner.calls) == 1


@pytest.mark.parametrize(
    "orders",
    [
        [1, 1],
        [1, 3],
    ],
)
def test_existing_at2_ordering_rules_reject_malformed_ordering(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any], orders: list[int]
) -> None:
    response = copy.deepcopy(valid_plan)
    response["slides"] = response["slides"][:2]
    for slide, order in zip(response["slides"], orders, strict=True):
        slide["order"] = order

    with pytest.raises(PresentationPlanValidationError, match="order"):
        plan_presentation(confirmed_framework, planner=MockPlanner(response))


def test_plan_without_process_flow_is_valid(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    response = copy.deepcopy(valid_plan)
    response["slides"] = [
        slide for slide in response["slides"] if slide["layoutId"] != "PROCESS_FLOW_01"
    ]
    for order, slide in enumerate(response["slides"], start=1):
        slide["order"] = order

    result = plan_presentation(confirmed_framework, planner=MockPlanner(response))

    assert all(slide.layoutId.value != "PROCESS_FLOW_01" for slide in result.slides)


def test_plan_with_exactly_one_process_flow_is_valid(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    result = plan_presentation(confirmed_framework, planner=MockPlanner(valid_plan))

    assert sum(slide.layoutId.value == "PROCESS_FLOW_01" for slide in result.slides) == 1


@pytest.mark.parametrize("duplicate_layout_id", ["PROCESS_FLOW_01", "CONTEXT_01", "SCOPE_01"])
def test_duplicate_layout_is_rejected_once_without_retry_or_silent_removal(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    duplicate_layout_id: str,
) -> None:
    response = copy.deepcopy(valid_plan)
    original_slide = next(
        slide for slide in response["slides"] if slide["layoutId"] == duplicate_layout_id
    )
    duplicate = copy.deepcopy(original_slide)
    duplicate["order"] = len(response["slides"]) + 1
    duplicate["purpose"] = f"duplicate {duplicate_layout_id}"
    response["slides"].append(duplicate)
    snapshot = copy.deepcopy(response)
    planner = MockPlanner(response)

    with pytest.raises(PresentationPlanValidationError, match=duplicate_layout_id):
        plan_presentation(confirmed_framework, planner=planner)

    assert len(planner.calls) == 1
    assert planner.calls[0]["retry_count"] == 0
    assert response == snapshot
    assert len(response["slides"]) == len(valid_plan["slides"]) + 1


def test_registry_validation_runs_before_duplicate_layout_validation(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = copy.deepcopy(valid_plan)
    duplicate = copy.deepcopy(response["slides"][1])
    duplicate["order"] = len(response["slides"]) + 1
    response["slides"].append(duplicate)
    registry_calls: list[dict[str, Any]] = []
    original_validator = planner_module.validate_registry_layout_selection

    def recording_registry_validator(payload: dict[str, Any]) -> None:
        registry_calls.append(copy.deepcopy(payload))
        original_validator(payload)

    monkeypatch.setattr(
        planner_module,
        "validate_registry_layout_selection",
        recording_registry_validator,
    )

    with pytest.raises(PresentationPlanValidationError, match="CONTEXT_01"):
        plan_presentation(confirmed_framework, planner=MockPlanner(response))

    assert registry_calls == [response]


def test_mocked_planning_is_deterministic_and_does_not_mutate_response(
    confirmed_framework: dict[str, Any], valid_plan: dict[str, Any]
) -> None:
    response_snapshot = copy.deepcopy(valid_plan)
    planner = MockPlanner(valid_plan)

    first = plan_presentation(confirmed_framework, planner=planner)
    second = plan_presentation(confirmed_framework, planner=planner)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert valid_plan == response_snapshot
    assert len(planner.calls) == 2

    first.title = "Changed after validation"
    first.slides[0].purpose = "changed"
    assert valid_plan == response_snapshot
    assert second.title == response_snapshot["title"]
    assert second.slides[0].purpose == response_snapshot["slides"][0]["purpose"]


def test_mocked_planning_requires_no_network_or_api_key(
    confirmed_framework: dict[str, Any],
    valid_plan: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    planner = MockPlanner(valid_plan)

    plan = plan_presentation(confirmed_framework, planner=planner)

    assert plan.title == valid_plan["title"]
    assert len(planner.calls) == 1
    assert "OPENAI_API_KEY" not in os.environ
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_planner_prompt_and_api_keep_stage_b_boundary_narrow() -> None:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").lower()
    normalized_prompt = " ".join(prompt.split())
    parameters = inspect.signature(plan_presentation).parameters

    assert list(parameters) == ["confirmed_framework", "planner"]
    assert "confirmed frameworkobject" in normalized_prompt
    assert re.search(r"\bdo not invent\b[^.]*\bfacts\b", normalized_prompt)
    assert (
        "pricing" in normalized_prompt
        and "currency" in normalized_prompt
        and "commercial" in normalized_prompt
    )
    assert "frameworkreferences" in normalized_prompt
    assert "layoutid" in normalized_prompt
    assert "coordinates" in normalized_prompt and "geometry" in normalized_prompt
    assert "each layoutid may appear at most once" in normalized_prompt
    assert "never use the same layoutid for two different slides" in normalized_prompt
    assert "process_flow_01 is optional and may appear zero or one time only" in normalized_prompt
    assert "do not add process_flow_01 merely because" in normalized_prompt
    assert "transcript" not in parameters
    assert "claude" not in parameters
    assert "chapter_layout_map" not in normalized_prompt
