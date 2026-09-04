from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.job_retry import is_transient_failure
from app.services.planning_job_errors import format_presentation_planning_failure
from llm.client import LlmClient, LlmUsageResult
from llm.openai_executor import OpenAIProviderError, OpenAIResponsesExecutor
from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaContentSlot,
    GammaGenerateRequest,
    GammaPayloadError,
)
from services.gamma.live_client import LiveGammaClient
from services.observability.llm_logger import LlmStage
from services.presentation.planner import PresentationPlanningCallError
from services.security.egress_audit import list_egress_decisions, reset_egress_decisions
from services.security import egress_policy as egress_policy_module
from services.security.egress_policy import (
    EgressBlockedError,
    enforce_external_egress,
    load_runtime_egress_policy,
    reset_egress_policy_cache,
    slot_classifications_from_policy,
)


@pytest.fixture(autouse=True)
def _reset_egress_audit() -> None:
    reset_egress_decisions()
    reset_egress_policy_cache()
    yield
    reset_egress_decisions()
    reset_egress_policy_cache()


def test_policy_approves_openai_anthropic_and_gamma() -> None:
    policy = load_runtime_egress_policy()
    assert policy.approved_providers == frozenset({"openai", "anthropic", "gamma"})


def test_enforce_allows_working_default_openai_planning_payload() -> None:
    payload = {
        "instructions": "Plan the deck",
        "frameworkObject": {"status": "confirmed", "chapters": [{"body": "Need invoice match"}]},
        "chapterLayoutGuidance": {"COVER_01": "Use cover"},
        "targetSchema": {"type": "object"},
    }

    filtered = enforce_external_egress(payload, provider="openai", stage="planning")

    assert filtered["frameworkObject"]["chapters"][0]["body"] == "Need invoice match"
    records = list_egress_decisions()
    assert len(records) == 1
    assert records[0].provider == "openai"
    assert "/frameworkObject/chapters/0/body" in records[0].allowed_paths
    dumped = repr(records[0].to_json_dict())
    assert "Need invoice match" not in dumped
    assert "Plan the deck" not in dumped


def test_enforce_blocks_unclassified_and_restricted_leaves() -> None:
    with pytest.raises(EgressBlockedError) as raised:
        enforce_external_egress(
            {
                "instructions": "Plan the deck",
                "secretStrategy": "Do not leave Borek",
            },
            provider="openai",
            stage="planning",
            extra_classifications={"/secretStrategy": "restricted"},
        )

    assert raised.value.code == "EGRESS_BLOCKED"
    assert raised.value.retryable is False
    assert "/secretStrategy" in raised.value.blocked_paths
    assert list_egress_decisions()[0].blocked_paths == ("/secretStrategy",)
    assert is_transient_failure(raised.value) is False


def test_stub_llm_client_does_not_require_classifications() -> None:
    client = LlmClient()
    result = client.complete_planning(planning_input={"unclassified": "fixture only"})
    assert result["schema_version"] == "1.0.0"
    assert list_egress_decisions() == []


def test_live_llm_client_filters_before_executor() -> None:
    seen: list[dict] = []

    def executor(*_args, request=None):
        seen.append(request or {})
        return LlmUsageResult(payload={"ok": True}, input_tokens=1, output_tokens=1)

    client = LlmClient(executor=executor, external_provider="openai")
    with pytest.raises(EgressBlockedError, match="secretStrategy"):
        client.complete_planning(
            planning_input={
                "instructions": "Plan",
                "targetSchema": {"type": "object"},
                "secretStrategy": "no",
            }
        )
    assert seen == []


def test_openai_executor_cannot_skip_the_filter() -> None:
    class FakeResponses:
        def create(self, **_kwargs):
            raise AssertionError("executor must not send a blocked payload")

    executor = OpenAIResponsesExecutor(
        api_key="sk-test",
        model="gpt-4.1-mini",
        client=SimpleNamespace(responses=FakeResponses()),
    )
    with pytest.raises(OpenAIProviderError) as raised:
        executor(
            LlmStage.PLANNING,
            "presentation_planner",
            "v1",
            0,
            request={
                "instructions": "Plan",
                "targetSchema": {"type": "object"},
                "secretStrategy": "no",
            },
        )
    assert raised.value.code == "EGRESS_BLOCKED"
    assert raised.value.retryable is False
    assert is_transient_failure(raised.value) is False


def test_planning_job_unwraps_egress_block_as_non_retryable() -> None:
    blocked = EgressBlockedError("openai", ("/secretStrategy",))
    wrapped = PresentationPlanningCallError(f"Presentation planning call failed: {blocked}")
    wrapped.__cause__ = blocked
    code, _message, retryable = format_presentation_planning_failure(wrapped)
    assert code == "EGRESS_BLOCKED"
    assert retryable is False


def test_anthropic_structured_complete_filters_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from llm.claude import client as claude_client

    captured: dict[str, str] = {}

    def fake_stream(create_kwargs, api_key):
        captured["system"] = create_kwargs["system"]
        captured["user"] = create_kwargs["messages"][0]["content"]
        return SimpleNamespace(
            stop_reason="end_turn",
            usage=None,
            content=[
                SimpleNamespace(type="tool_use", name="submit_customer_report", input={"ok": True})
            ],
        )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(claude_client, "_stream_final_message", fake_stream)
    result = claude_client.structured_complete(
        "Borek system",
        "Redacted transcript",
        {"type": "object"},
        tool_name="submit_customer_report",
        tool_description="Submit",
    )
    assert result == {"ok": True}
    assert captured["system"] == "Borek system"
    assert captured["user"] == "Redacted transcript"
    assert list_egress_decisions()[0].provider == "anthropic"


def test_anthropic_blocks_restricted_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from llm.claude import client as claude_client

    def fake_stream(_create_kwargs, _api_key):
        raise AssertionError("Anthropic must not be called with a blocked payload")

    def blocked_enforce(*_args, **_kwargs):
        raise EgressBlockedError("anthropic", ("/user",))

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(claude_client, "_stream_final_message", fake_stream)
    monkeypatch.setattr(
        "services.security.egress_policy.enforce_external_egress",
        blocked_enforce,
    )
    with pytest.raises(claude_client.ClaudeClientError) as raised:
        claude_client.structured_complete(
            "system",
            "restricted user text",
            {"type": "object"},
            tool_name="submit_customer_report",
            tool_description="Submit",
        )
    assert raised.value.code == "EGRESS_BLOCKED"
    assert raised.value.retryable is False


def test_gamma_slot_policy_classifies_provisional_slots() -> None:
    classified = slot_classifications_from_policy(
        ("cover.title", "cover.client_name", "context.summary")
    )
    assert classified["cover.title"] == "internal"
    assert classified["cover.client_name"] == "client_confidential"
    assert "unknown.slot" not in slot_classifications_from_policy(("unknown.slot",))


def test_live_gamma_client_blocks_unclassified_before_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = dict(egress_policy_module._raw_policy())
    fields = dict(raw.get("field_classifications") or {})
    fields.pop("/slots/cover.client_name", None)
    raw["field_classifications"] = fields
    reset_egress_policy_cache()
    monkeypatch.setattr(egress_policy_module, "_raw_policy", lambda: raw)

    class FakeHttp:
        def request(self, *_args, **_kwargs):
            raise AssertionError("Gamma HTTP must not run for a blocked slot")

        def close(self) -> None:
            return None

    client = LiveGammaClient(
        api_key="sk-gamma-test",
        theme_id="theme-1",
        http_client=FakeHttp(),  # type: ignore[arg-type]
    )
    with pytest.raises(GammaPayloadError, match="cover.client_name"):
        client.generate(
            GammaGenerateRequest(
                template_id=LOCKED_BOREK_TEMPLATE_ID,
                template_version=LOCKED_BOREK_TEMPLATE_VERSION,
                opportunity_id="opp-1",
                presentation_version_id="version-1",
                output_formats=("pptx",),
                slots=(
                    GammaContentSlot("cover.title", "Invoice match"),
                    GammaContentSlot("cover.client_name", "must not leave"),
                ),
            )
        )
    assert "/slots/cover.client_name" in list_egress_decisions()[0].blocked_paths
