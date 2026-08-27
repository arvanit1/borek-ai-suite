"""AT-53: AI observability logging tests."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path

import pytest

from llm.client import LlmClient, LlmUsageResult
from services.observability.llm_logger import (
    FORBIDDEN_LOG_FIELD_NAMES,
    LlmStage,
    get_llm_call_logs,
    invoke_llm,
    log_llm_call,
    reset_llm_call_logs,
)
from services.slides.content_generation.group_a.common import StructuredGenerationRequest

CLIENT_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / "llm" / "client.py"
LOGGER_PATH = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "api"
    / "services"
    / "observability"
    / "llm_logger.py"
)

CANONICAL_STAGES = frozenset(stage.value for stage in LlmStage)


@pytest.fixture(autouse=True)
def _reset_logs() -> None:
    reset_llm_call_logs()


def test_log_llm_call_persists_required_metadata_fields() -> None:
    request_id = uuid.uuid4()
    entry = log_llm_call(
        request_id=request_id,
        stage=LlmStage.FRAMEWORK,
        model="claude-sonnet-4",
        prompt_version="synthesis_v1",
        input_tokens=1200,
        output_tokens=800,
        latency_ms=1534.2,
        retry_count=1,
    )

    assert entry.request_id == request_id
    assert entry.stage == "framework"
    assert entry.model == "claude-sonnet-4"
    assert entry.prompt_version == "synthesis_v1"
    assert entry.input_tokens == 1200
    assert entry.output_tokens == 800
    assert entry.total_tokens == 2000
    assert entry.latency_ms == 1534.2
    assert entry.retry_count == 1
    assert entry.timestamp is not None


def test_log_llm_call_rejects_confidential_fields() -> None:
    with pytest.raises(ValueError, match="confidential fields"):
        log_llm_call(
            request_id=uuid.uuid4(),
            stage=LlmStage.COMPRESSION,
            model="gpt-4.1-mini",
            prompt_version="compression_v1",
            input_tokens=10,
            output_tokens=5,
            latency_ms=12.0,
            retry_count=0,
            prompt="secret transcript text",
        )


def test_invoke_llm_records_metadata_without_payload() -> None:
    secret_payload = {"messages": [{"role": "user", "content": "confidential transcript"}]}

    result = invoke_llm(
        stage=LlmStage.PLANNING,
        model="gpt-4.1-mini",
        prompt_version="presentation_planner_v1",
        retry_count=2,
        call=lambda: secret_payload,
        input_tokens=lambda _: 256,
        output_tokens=lambda _: 128,
    )

    assert result == secret_payload
    entries = get_llm_call_logs()
    assert len(entries) == 1
    stored = asdict(entries[0])
    assert stored["stage"] == "planning"
    assert stored["retry_count"] == 2
    assert stored["input_tokens"] == 256
    assert stored["output_tokens"] == 128
    assert stored["total_tokens"] == 384
    assert "messages" not in stored
    assert "content" not in stored
    for forbidden in FORBIDDEN_LOG_FIELD_NAMES:
        assert forbidden not in stored


@pytest.mark.parametrize(
    ("method_name", "expected_stage"),
    [
        ("complete_framework", LlmStage.FRAMEWORK),
        ("complete_planning", LlmStage.PLANNING),
    ],
)
def test_llm_client_direct_methods_log_each_stage(method_name: str, expected_stage: LlmStage) -> None:
    client = LlmClient()
    getattr(client, method_name)(prompt_version="test_v1", retry_count=0)

    entries = get_llm_call_logs()
    assert len(entries) == 1
    assert entries[0].stage == expected_stage.value
    assert entries[0].prompt_version == "test_v1"


def test_llm_client_structured_generator_logs_slide_generation_stage() -> None:
    client = LlmClient()
    generator = client.structured_generator(prompt_version="context_01_v1", retry_count=0)
    request = StructuredGenerationRequest(
        layout_id="CONTEXT_01",
        chapters=({"chapter_id": "1", "title": "Context", "body": [{"summary": "Grounded"}]},),
        target_schema={"type": "object"},
        instructions="Generate grounded content only.",
    )
    generator(request)

    entries = get_llm_call_logs()
    assert len(entries) == 1
    assert entries[0].stage == LlmStage.SLIDE_GENERATION.value


def test_llm_client_compression_fn_logs_compression_stage() -> None:
    client = LlmClient()
    compress = client.compression_fields_fn(prompt_version="compression_v1", retry_count=1)
    compress({"title": "A very long title that exceeds limits"}, [])

    entries = get_llm_call_logs()
    assert len(entries) == 1
    assert entries[0].stage == LlmStage.COMPRESSION.value
    assert entries[0].retry_count == 1
    assert entries[0].prompt_version == "compression_v1"


def test_llm_client_covers_all_required_pipeline_stages() -> None:
    client = LlmClient()
    client.complete_framework()
    client.complete_planning()
    client.structured_generator()(
        StructuredGenerationRequest(
            layout_id="COVER_01",
            chapters=({"chapter_id": "0", "title": "Cover", "body": []},),
            target_schema={"type": "object"},
            instructions="Cover slide",
        )
    )
    client.compression_fields_fn()({"title": "Long title value"}, [])

    recorded_stages = {entry.stage for entry in get_llm_call_logs()}
    assert recorded_stages == CANONICAL_STAGES


def test_llm_client_executor_can_supply_token_counts() -> None:
    def counting_executor(stage, operation, prompt_version, retry_count):
        _ = (stage, operation, prompt_version, retry_count)
        return LlmUsageResult(payload={"ok": True}, input_tokens=42, output_tokens=21)

    client = LlmClient(executor=counting_executor)
    client.complete_framework()

    entry = get_llm_call_logs()[0]
    assert entry.input_tokens == 42
    assert entry.output_tokens == 21
    assert entry.total_tokens == 63


def test_observability_module_exists_at_expected_path() -> None:
    assert LOGGER_PATH.is_file()
    source = LOGGER_PATH.read_text(encoding="utf-8")
    assert "def log_llm_call" in source
    assert "def invoke_llm" in source
    assert "request_id" in source
    assert "latency_ms" in source
    assert "retry_count" in source


def test_llm_client_routes_all_calls_through_invoke_llm() -> None:
    source = CLIENT_PATH.read_text(encoding="utf-8")
    assert "from services.observability.llm_logger import" in source
    assert source.count("invoke_llm(") >= 4
