"""Live OpenAI slide generation and compression without network access."""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import settings
from app.services import stage_b_orchestration as stage_b
from app.services import stage_b_providers
from app.services.data.memory_store import MemoryDataStore
from llm.client import LlmClient, LlmUsageResult
from llm.json_schema_bundle import prepare_openai_json_schema
from llm.openai_executor import (
    OpenAIProviderConfigurationError,
    OpenAIResponsesExecutor,
    OpenAISlideGenerationResponseError,
)
from services.observability.llm_logger import (
    LlmStage,
    get_llm_call_logs,
    reset_llm_call_logs,
)
from services.slides.content_generation.group_a.common import (
    StructuredGenerationFailure,
    StructuredGenerationRequest,
)
from services.slides.content_generation.group_a.cover_01 import generate_cover_01
from services.validation.constraint_validator import ConstraintViolation

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
COVER_FIXTURE_PATH = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a" / "cover_01.realistic.json"
)
COVER_SCHEMA_PATH = (
    ROOT / "packages" / "contracts" / "slide_spec" / "group_a" / "cover_01.schema.json"
)
COMPRESSION_PROMPT_PATH = (
    ROOT / "apps" / "api" / "llm" / "openai" / "prompts" / "slide_compression_v1.txt"
)
ORIGINAL_STRUCTURED = stage_b.get_live_structured_generator
ORIGINAL_COMPRESSION = stage_b.get_live_compression_fields


def _framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_PATH.read_text(encoding="utf-8"))


def _cover_fixture() -> dict[str, Any]:
    return json.loads(COVER_FIXTURE_PATH.read_text(encoding="utf-8"))


def _cover_schema() -> dict[str, Any]:
    return json.loads(COVER_SCHEMA_PATH.read_text(encoding="utf-8"))


class FakeResponses:
    def __init__(
        self,
        payload: dict[str, Any],
        *,
        input_tokens: int = 210,
        output_tokens: int = 88,
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
            id="resp_slide_test",
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


def _cover_request() -> dict[str, Any]:
    return {
        "instructions": "Generate a grounded COVER_01 SlideSpec.",
        "layoutId": "COVER_01",
        "chapters": [
            {"chapter_id": "1", "title": "Context", "body": [{"summary": "Grounded"}]}
        ],
        "targetSchema": _cover_schema(),
    }


def test_fixture_mode_does_not_construct_openai_slide_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "fixture")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(
        stage_b_providers,
        "build_live_structured_generator",
        lambda: pytest.fail("fixture mode constructed the live slide client"),
    )
    monkeypatch.setattr(
        stage_b_providers,
        "build_live_compression_fields",
        lambda: pytest.fail("fixture mode constructed the live compression client"),
    )

    assert ORIGINAL_STRUCTURED() is stage_b_providers.fixture_structured_generate
    assert ORIGINAL_COMPRESSION() is stage_b_providers.fixture_compress_fields


def test_live_mode_returns_llm_slide_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[dict[str, str]] = []

    class FakeExecutor:
        def __init__(self, *, api_key: str, model: str) -> None:
            constructed.append({"api_key": api_key, "model": model})

        def __call__(self, *_args: Any, **_kwargs: Any) -> LlmUsageResult:
            return LlmUsageResult(payload=_cover_fixture(), input_tokens=1, output_tokens=1)

    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "live")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-live-test")
    monkeypatch.setattr(settings, "OPENAI_PRESENTATION_MODEL", "gpt-4.1-mini")
    monkeypatch.setattr("llm.openai_executor.OpenAIResponsesExecutor", FakeExecutor)

    generator = ORIGINAL_STRUCTURED()
    compress = ORIGINAL_COMPRESSION()

    assert callable(generator)
    assert callable(compress)
    assert constructed == [
        {"api_key": "sk-live-test", "model": "gpt-4.1-mini"},
        {"api_key": "sk-live-test", "model": "gpt-4.1-mini"},
    ]


def test_live_mode_missing_openai_key_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AI_EXECUTION_MODE", "live")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    with pytest.raises(OpenAIProviderConfigurationError, match="OPENAI_API_KEY"):
        ORIGINAL_STRUCTURED()
    with pytest.raises(OpenAIProviderConfigurationError, match="OPENAI_API_KEY"):
        ORIGINAL_COMPRESSION()


_OPENAI_ROOT_FORBIDDEN = frozenset({"oneOf", "anyOf", "allOf", "enum", "const", "not"})
_LAYOUT_SCHEMA_PATHS = tuple(
    sorted(
        (ROOT / "packages" / "contracts" / "slide_spec").glob("*/*.schema.json")
    )
)


def test_cover_schema_is_openai_legal_object() -> None:
    bundled = prepare_openai_json_schema(_cover_schema())
    dumped = json.dumps(bundled)

    assert "base.schema.json" not in dumped
    assert bundled["type"] == "object"
    assert _OPENAI_ROOT_FORBIDDEN.isdisjoint(bundled)
    assert bundled["properties"]["title"]["type"] == "string"
    assert bundled["properties"]["title"]["maxLength"] == 60
    assert bundled["properties"]["layoutId"]["const"] == "COVER_01"
    assert bundled["properties"]["statBadges"]["minItems"] == 1
    assert bundled["properties"]["statBadges"]["maxItems"] == 3
    assert bundled["properties"]["statBadges"]["items"]["properties"]["value"]["maxLength"] == 16
    assert "sourceChapterIds" in bundled["properties"]


@pytest.mark.parametrize("schema_path", _LAYOUT_SCHEMA_PATHS, ids=lambda path: path.stem)
def test_every_layout_schema_is_openai_legal_at_the_root(schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    prepared = prepare_openai_json_schema(schema)

    assert prepared["type"] == "object"
    assert _OPENAI_ROOT_FORBIDDEN.isdisjoint(prepared)
    assert "base.schema.json" not in json.dumps(prepared)
    layout_id = prepared["properties"]["layoutId"]["const"]
    if layout_id == "COVER_01":
        assert prepared["properties"]["statBadges"]["maxItems"] == 3


def test_openai_slide_call_uses_bundled_schema_and_chapters_only() -> None:
    executor, responses = _executor(_cover_fixture())
    request = _cover_request()

    result = executor(
        LlmStage.SLIDE_GENERATION,
        "COVER_01",
        "slide_structured_v1",
        0,
        request=request,
    )

    assert result.payload == _cover_fixture()
    assert result.input_tokens == 210
    assert result.output_tokens == 88
    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call["model"] == "gpt-4.1-mini"
    assert call["instructions"] == request["instructions"]
    assert call["store"] is False
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["name"] == "COVER_01"
    assert call["text"]["format"]["strict"] is False
    sent_schema = call["text"]["format"]["schema"]
    assert sent_schema["type"] == "object"
    assert _OPENAI_ROOT_FORBIDDEN.isdisjoint(sent_schema)
    assert sent_schema["properties"]["statBadges"]["maxItems"] == 3
    assert "base.schema.json" not in json.dumps(sent_schema)
    sent_input = json.loads(call["input"])
    assert sent_input == {
        "layoutId": "COVER_01",
        "chapters": request["chapters"],
        "targetSchema": request["targetSchema"],
    }
    assert "transcript" not in sent_input
    assert "claude" not in sent_input
    assert "instructions" not in sent_input


def test_llm_client_passes_structured_request_to_executor() -> None:
    reset_llm_call_logs()
    secret = "sk-must-not-be-logged"
    executor, responses = _executor(_cover_fixture(), api_key=secret)
    client = LlmClient(model="gpt-4.1-mini", executor=executor)
    request = StructuredGenerationRequest(
        layout_id="COVER_01",
        chapters=({"chapter_id": "1", "title": "Context", "body": [{"summary": "Grounded"}]},),
        target_schema=_cover_schema(),
        instructions="Generate a grounded COVER_01 SlideSpec.",
    )

    payload = client.structured_generator(prompt_version="slide_structured_v1")(request)

    assert payload == _cover_fixture()
    assert len(responses.calls) == 1
    logs = get_llm_call_logs()
    assert len(logs) == 1
    assert logs[0].stage == LlmStage.SLIDE_GENERATION.value
    assert logs[0].prompt_version == "slide_structured_v1"
    assert secret not in repr([asdict(log) for log in logs])


def test_group_a_cover_makes_one_openai_call_and_validates() -> None:
    reset_llm_call_logs()
    executor, responses = _executor(_cover_fixture())
    client = LlmClient(model="gpt-4.1-mini", executor=executor)

    result = generate_cover_01(
        _framework(),
        structured_generate=client.structured_generator(prompt_version="slide_structured_v1"),
        compress_fields=lambda offending, _violations: copy.deepcopy(offending),
    )

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["layoutId"] == "COVER_01"
    assert len(responses.calls) == 1
    sent_input = json.loads(responses.calls[0]["input"])
    assert sent_input["layoutId"] == "COVER_01"
    assert all(chapter["chapter_id"] == "1" for chapter in sent_input["chapters"])
    assert "transcript" not in json.dumps(sent_input)


def test_openai_slide_error_has_no_fixture_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor, responses = _executor(
        _cover_fixture(),
        error=RuntimeError("OpenAI transport unavailable"),
    )
    client = LlmClient(model="gpt-4.1-mini", executor=executor)
    store = MemoryDataStore()
    user_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
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
    plan = store.create_presentation_plan(
        framework_version_id=framework["id"],
        user_id=user_id,
        plan_json={
            "schema_version": "1.0",
            "title": "Cover only",
            "slides": [
                {
                    "order": 1,
                    "purpose": "cover",
                    "layoutId": "COVER_01",
                    "frameworkReferences": ["chapter_1"],
                }
            ],
        },
    )
    presentation = store.create_presentation(
        presentation_plan_id=plan["id"],
        user_id=user_id,
        name="Cover",
    )
    monkeypatch.setattr(stage_b, "get_live_structured_generator", lambda: client.structured_generator())
    monkeypatch.setattr(
        stage_b,
        "get_live_compression_fields",
        lambda: (lambda offending, _violations: copy.deepcopy(offending)),
    )

    with pytest.raises(StructuredGenerationFailure, match="transport unavailable"):
        store.create_presentation_version_with_slides(
            presentation_id=presentation["id"],
            user_id=user_id,
            plan_json=plan["plan_json"],
        )

    assert len(responses.calls) == 1
    assert store.slides == {}


def test_compression_sends_only_offending_paths() -> None:
    rewritten = {"$.title": "Short title"}
    executor, responses = _executor(rewritten)
    client = LlmClient(model="gpt-4.1-mini", executor=executor)
    compress = client.compression_fields_fn(
        prompt_version="slide_compression_v1",
        instructions="Shorten overflowing fields.",
    )
    violations = [
        ConstraintViolation(path="$.title", code="max_length", message="too long", limit=40)
    ]

    result = compress({"$.title": "X" * 80}, violations)

    assert result == rewritten
    assert len(responses.calls) == 1
    sent_input = json.loads(responses.calls[0]["input"])
    assert sent_input["offendingValues"] == {"$.title": "X" * 80}
    assert sent_input["violations"] == [
        {
            "path": "$.title",
            "code": "max_length",
            "message": "too long",
            "limit": 40,
        }
    ]
    assert sent_input["targetSchema"]["required"] == ["$.title"]
    assert sent_input["targetSchema"]["properties"]["$.title"]["maxLength"] == 40
    assert "instructions" not in sent_input
    assert "at most 40 characters" in responses.calls[0]["instructions"]
    assert responses.calls[0]["text"]["format"]["name"] == "compressed_fields"


def _run_bt_compression(
    *,
    offending: dict[str, str],
    rewritten: dict[str, str],
    limits: dict[str, int],
) -> tuple[dict[str, str], FakeResponses]:
    executor, responses = _executor(rewritten)
    client = LlmClient(model="gpt-4.1-mini", executor=executor)
    compress = client.compression_fields_fn(
        prompt_version="slide_compression_v1",
        instructions=COMPRESSION_PROMPT_PATH.read_text(encoding="utf-8"),
    )
    violations = [
        ConstraintViolation(
            path=path,
            code="max_length",
            message="too long",
            limit=limit,
        )
        for path, limit in limits.items()
    ]
    return compress(offending, violations), responses


def test_context_compression_receives_complete_sentence_rewrite_guidance() -> None:
    original = (
        "Analysts currently spend substantial time manually comparing 1.200 "
        "invoices, purchase orders and goods receipts across different systems "
        "during every daily processing cycle without a unified workflow."
    )
    result, responses = _run_bt_compression(
        offending={"problem.description": original},
        rewritten={"problem.description": "Analysts manually compare 1200 invoices."},
        limits={"problem.description": 160},
    )

    assert result == {
        "problem.description": "Analysts manually compare 1.200 invoices."
    }
    assert len(responses.calls) == 1
    instructions = " ".join(responses.calls[0]["instructions"].split()).lower()
    assert "one concise complete sentence" in instructions
    assert "never merely return a prefix" in instructions
    assert "preserve source number forms" in instructions
    assert "at most 160 characters" in instructions
    request = json.loads(responses.calls[0]["input"])
    assert request["targetSchema"]["properties"]["problem.description"][
        "maxLength"
    ] == 160


def test_scope_compression_preserves_included_and_later_semantics() -> None:
    result, responses = _run_bt_compression(
        offending={
            "included[0]": (
                "Automate standard matching while retaining controls and review "
                "across all source systems."
            ),
            "later[0]": (
                "Supplier-response tracking remains planned for a later phase "
                "after the core rollout."
            ),
        },
        rewritten={
            "included[0]": "Automate standard matching with review controls.",
            "later[0]": "Add supplier-response tracking later.",
            "unexpected.path": "must be ignored",
        },
        limits={"included[0]": 72, "later[0]": 72},
    )

    assert result == {
        "included[0]": "Automate standard matching with review controls.",
        "later[0]": "Add supplier-response tracking later.",
    }
    assert len(responses.calls) == 1
    instructions = " ".join(responses.calls[0]["instructions"].split()).lower()
    assert "self-contained scope statement" in instructions
    assert "`included[i]` must remain explicitly in scope" in instructions
    assert "`later[i]` must remain explicitly later or future scope" in instructions
    request = json.loads(responses.calls[0]["input"])
    assert set(request["targetSchema"]["required"]) == {"included[0]", "later[0]"}
    assert set(result) == set(request["offendingValues"])


def test_requirement_compression_preserves_requirement_and_never_rewrites_status() -> None:
    result, responses = _run_bt_compression(
        offending={
            "requirements[0].category": "Data validation controls",
            "requirements[0].title": (
                "Flag duplicate invoice numbers for mandatory review before approval."
            ),
        },
        rewritten={
            "requirements[0].category": "Validation",
            "requirements[0].title": "Flag duplicate invoice numbers for review.",
            "requirements[0].status": "later",
        },
        limits={"requirements[0].category": 12, "requirements[0].title": 48},
    )

    assert result == {
        "requirements[0].category": "Validation",
        "requirements[0].title": "Flag duplicate invoice numbers for review.",
    }
    assert "requirements[0].status" not in result
    assert len(responses.calls) == 1
    instructions = " ".join(responses.calls[0]["instructions"].split()).lower()
    assert "concise, complete requirement statement" in instructions
    assert "never rewrite `requirements[i].status`" in instructions
    assert "included`, `partial`, and `later`" in instructions


def test_unknown_compression_path_uses_shared_safe_rewrite_rules() -> None:
    result, responses = _run_bt_compression(
        offending={"unrelated.note": "A long but grounded note requiring compression."},
        rewritten={
            "unrelated.note": "A concise grounded note.",
            "new.path": "not allowed",
        },
        limits={"unrelated.note": 32},
    )

    assert result == {"unrelated.note": "A concise grounded note."}
    assert len(responses.calls) == 1
    instructions = " ".join(responses.calls[0]["instructions"].split()).lower()
    assert "rewrite and paraphrase" in instructions
    assert "do not add paths" in instructions
    assert "introduce no new fact" in instructions
    assert "never use an ellipsis" in instructions


def test_compression_does_not_silently_clip_overlong_model_output() -> None:
    overlong = "invoice matching is still entirely manual today " * 6
    assert len(overlong) > 160
    executor, _responses = _executor({"problem.description": overlong})
    client = LlmClient(model="gpt-4.1-mini", executor=executor)
    compress = client.compression_fields_fn(prompt_version="slide_compression_v1")
    violations = [
        ConstraintViolation(
            path="problem.description",
            code="max_length",
            message="too long",
            limit=160,
        )
    ]

    result = compress({"problem.description": "X" * 192}, violations)

    fitted = result["problem.description"]
    assert fitted == overlong
    assert len(fitted) > 160


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
def test_incomplete_refused_or_empty_slide_response_fails_closed(response: Any) -> None:
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: response)
    )
    executor = OpenAIResponsesExecutor(
        api_key="sk-test",
        model="gpt-4.1-mini",
        client=fake_client,
    )

    with pytest.raises(OpenAISlideGenerationResponseError):
        executor(
            LlmStage.SLIDE_GENERATION,
            "COVER_01",
            "slide_structured_v1",
            0,
            request=_cover_request(),
        )
