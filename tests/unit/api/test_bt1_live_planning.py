"""BT-1 live OpenAI planning integration without network access."""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import Settings, settings
from app.services import stage_b_orchestration as stage_b
from app.services import stage_b_providers
from app.services.data.memory_store import MemoryDataStore
from llm.client import LlmClient, LlmUsageResult
from llm.openai_executor import (
    OpenAIPlanningResponseError,
    OpenAIProviderConfigurationError,
    OpenAIResponsesExecutor,
)
from services.observability.llm_logger import (
    LlmStage,
    get_llm_call_logs,
    reset_llm_call_logs,
)
from services.presentation.planner import (
    PresentationPlanValidationError,
    PresentationPlanningCallError,
    plan_presentation,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
PLAN_PATH = ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"
PLAN_SCHEMA_PATH = ROOT / "packages" / "contracts" / "presentation_plan.schema.json"
ORIGINAL_PLANNING_FACTORY = stage_b.get_live_planning_client


def _framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_PATH.read_text(encoding="utf-8"))


def _valid_plan() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _plan_schema() -> dict[str, Any]:
    return json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))


class FakeResponses:
    def __init__(
        self,
        payload: dict[str, Any],
        *,
        input_tokens: int = 321,
        output_tokens: int = 123,
        error: Exception | None = None,
    ) -> None:
        self.payload = copy.deepcopy(payload)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(copy.deepcopy(kwargs))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            id="resp_test",
            status="completed",
            error=None,
            incomplete_details=None,
            output=[],
            output_text=json.dumps(self.payload),
            usage=SimpleNamespace(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
            ),
        )


class FakeOpenAIClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def _executor(
    payload: dict[str, Any],
    *,
    api_key: str = "sk-test-secret",
    error: Exception | None = None,
) -> tuple[OpenAIResponsesExecutor, FakeResponses]:
    responses = FakeResponses(payload, error=error)
    return (
        OpenAIResponsesExecutor(
            api_key=api_key,
            model="gpt-4.1-mini",
            client=FakeOpenAIClient(responses),
        ),
        responses,
    )


def _memory_store_with_framework() -> tuple[MemoryDataStore, uuid.UUID, uuid.UUID]:
    user_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    store = MemoryDataStore()
    opportunity = store.create_opportunity(
        user_id=user_id,
        client_name="Acme",
        opportunity_name="Invoice automation",
        department="Finance",
        language="en",
    )
    framework_json = _framework()
    framework_json["opportunity_id"] = str(opportunity["id"])
    framework = store.create_framework_version(
        opportunity_id=opportunity["id"],
        user_id=user_id,
        framework_json=framework_json,
        status="confirmed",
    )
    return store, user_id, framework["id"]


def test_fixture_mode_does_not_construct_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(
        stage_b_providers,
        "build_live_planning_client",
        lambda: pytest.fail("fixture mode constructed the live OpenAI client"),
    )

    planner = ORIGINAL_PLANNING_FACTORY()

    assert isinstance(planner, stage_b_providers.FixturePlanningClient)
    assert planner.complete_planning() == stage_b_providers._FIXTURE_PLAN


def test_fixture_planner_remains_valid_under_unique_layout_rules() -> None:
    plan = plan_presentation(
        _framework(),
        planner=stage_b_providers.FixturePlanningClient(),
    )

    layout_ids = [slide.layoutId.value for slide in plan.slides]
    assert len(layout_ids) == len(set(layout_ids))
    assert "PROCESS_FLOW_01" not in layout_ids


def test_fixture_settings_do_not_require_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    fixture_settings = Settings(_env_file=None, AI_EXECUTION_MODE="fixture")

    assert fixture_settings.OPENAI_API_KEY == ""


def test_live_mode_returns_real_llm_planning_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[dict[str, str]] = []

    class FakeExecutor:
        def __init__(self, *, api_key: str, model: str) -> None:
            constructed.append({"api_key": api_key, "model": model})

        def __call__(self, *_args: Any, **_kwargs: Any) -> LlmUsageResult:
            return LlmUsageResult(payload=_valid_plan(), input_tokens=1, output_tokens=1)

    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "live")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-live-test")
    monkeypatch.setattr(settings, "OPENAI_PRESENTATION_MODEL", "gpt-4.1-mini")
    monkeypatch.setattr("llm.openai_executor.OpenAIResponsesExecutor", FakeExecutor)

    planner = ORIGINAL_PLANNING_FACTORY()

    assert isinstance(planner, LlmClient)
    assert constructed == [
        {"api_key": "sk-live-test", "model": "gpt-4.1-mini"}
    ]


def test_live_mode_missing_openai_key_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "live")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    with pytest.raises(OpenAIProviderConfigurationError, match="OPENAI_API_KEY"):
        ORIGINAL_PLANNING_FACTORY()


def test_openai_responses_uses_canonical_schema_and_actual_usage() -> None:
    executor, responses = _executor(_valid_plan())
    request = {
        "instructions": "Create a grounded PresentationPlan.",
        "frameworkObject": _framework(),
        "chapterLayoutGuidance": {"chapters": []},
        "targetSchema": _plan_schema(),
    }

    result = executor(
        LlmStage.PLANNING,
        "presentation_planner",
        "presentation_planner_v2",
        0,
        request=request,
    )

    assert result.payload == _valid_plan()
    assert result.input_tokens == 321
    assert result.output_tokens == 123
    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call["model"] == "gpt-4.1-mini"
    assert call["instructions"] == request["instructions"]
    assert call["store"] is False
    assert call["text"]["format"] == {
        "type": "json_schema",
        "name": "presentation_plan",
        "schema": _plan_schema(),
        "strict": False,
    }
    sent_input = json.loads(call["input"])
    assert sent_input == {
        "frameworkObject": request["frameworkObject"],
        "chapterLayoutGuidance": request["chapterLayoutGuidance"],
        "targetSchema": request["targetSchema"],
    }
    assert "transcript" not in sent_input
    assert "claude" not in sent_input


def test_confirmed_framework_makes_one_openai_call_and_flows_through_bt1_validation() -> None:
    reset_llm_call_logs()
    secret = "sk-must-not-be-logged"
    executor, responses = _executor(_valid_plan(), api_key=secret)
    planner = LlmClient(model="gpt-4.1-mini", executor=executor)

    plan = plan_presentation(_framework(), planner=planner)

    assert plan.model_dump(mode="json") == _valid_plan()
    assert len(responses.calls) == 1
    sent_input = json.loads(responses.calls[0]["input"])
    assert sent_input["frameworkObject"]["status"] == "confirmed"
    assert "chapterLayoutGuidance" in sent_input
    logs = get_llm_call_logs()
    assert len(logs) == 1
    assert logs[0].stage == LlmStage.PLANNING.value
    assert logs[0].model == "gpt-4.1-mini"
    assert logs[0].prompt_version == "presentation_planner_v2"
    assert logs[0].retry_count == 0
    assert logs[0].input_tokens == 321
    assert logs[0].output_tokens == 123
    assert logs[0].latency_ms >= 0
    assert logs[0].request_id is not None
    assert secret not in repr([asdict(log) for log in logs])


def test_invalid_openai_plan_is_not_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_plan = {"schema_version": "1.0", "title": "Invalid", "slides": []}
    executor, responses = _executor(invalid_plan)
    planner = LlmClient(model="gpt-4.1-mini", executor=executor)
    store, user_id, framework_id = _memory_store_with_framework()
    monkeypatch.setattr(stage_b, "get_live_planning_client", lambda: planner)

    with pytest.raises(PresentationPlanValidationError):
        store.generate_presentation_plan(
            framework_version_id=framework_id,
            user_id=user_id,
        )

    assert len(responses.calls) == 1
    assert store.presentation_plans == {}


def test_openai_provider_error_has_no_fixture_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor, responses = _executor(
        _valid_plan(),
        error=RuntimeError("OpenAI transport unavailable"),
    )
    planner = LlmClient(model="gpt-4.1-mini", executor=executor)
    store, user_id, framework_id = _memory_store_with_framework()
    monkeypatch.setattr(stage_b, "get_live_planning_client", lambda: planner)

    with pytest.raises(PresentationPlanningCallError, match="transport unavailable"):
        store.generate_presentation_plan(
            framework_version_id=framework_id,
            user_id=user_id,
        )

    assert len(responses.calls) == 1
    assert store.presentation_plans == {}


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(
            status="incomplete",
            error=None,
            incomplete_details={"reason": "max_output_tokens"},
            output=[],
            output_text="",
            usage=None,
        ),
        SimpleNamespace(
            status="completed",
            error=None,
            incomplete_details=None,
            output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
            output_text="",
            usage=None,
        ),
        SimpleNamespace(
            status="completed",
            error=None,
            incomplete_details=None,
            output=[],
            output_text="",
            usage=None,
        ),
    ],
)
def test_incomplete_refused_or_empty_openai_response_fails_closed(response: Any) -> None:
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: response)
    )
    executor = OpenAIResponsesExecutor(
        api_key="sk-test",
        model="gpt-4.1-mini",
        client=fake_client,
    )

    with pytest.raises(OpenAIPlanningResponseError):
        executor(
            LlmStage.PLANNING,
            "presentation_planner",
            "presentation_planner_v2",
            0,
            request={
                "instructions": "Plan.",
                "frameworkObject": _framework(),
                "chapterLayoutGuidance": {},
                "targetSchema": _plan_schema(),
            },
        )
