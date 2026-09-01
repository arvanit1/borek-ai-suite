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


def test_llm_call_record_to_json_dict_is_json_safe() -> None:
    request_id = uuid.uuid4()
    job_id = uuid.uuid4()
    opportunity_id = uuid.uuid4()
    entry = log_llm_call(
        request_id=request_id,
        stage=LlmStage.FRAMEWORK,
        model="claude-sonnet-4",
        prompt_version="synthesis_v1",
        input_tokens=1200,
        output_tokens=800,
        latency_ms=1534.2,
        retry_count=1,
        job_id=job_id,
        opportunity_id=opportunity_id,
    )
    payload = entry.to_json_dict()
    import json

    json.dumps(payload)
    assert payload["request_id"] == str(request_id)
    assert payload["job_id"] == str(job_id)
    assert payload["opportunity_id"] == str(opportunity_id)


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


REQUIRED_LLM_CALL_FIELDS = (
    "request_id",
    "job_id",
    "opportunity_id",
    "stage",
    "provider",
    "model",
    "prompt_version",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_ms",
    "retry_count",
    "status",
    "error_category",
    "estimated_cost_eur",
)


def test_llm_call_persisted_to_store() -> None:
    from unittest.mock import MagicMock

    from services.observability.llm_logger import llm_observability_scope

    store = MagicMock()
    job_id = uuid.uuid4()
    opportunity_id = uuid.uuid4()
    with llm_observability_scope(job_id=job_id, opportunity_id=opportunity_id, store=store):
        invoke_llm(
            stage=LlmStage.FRAMEWORK,
            model="claude-sonnet-4",
            prompt_version="synthesis_v1",
            retry_count=0,
            call=lambda: {"ok": True},
            input_tokens=lambda _: 100,
            output_tokens=lambda _: 50,
        )

    store.append_llm_call.assert_called_once()
    record = store.append_llm_call.call_args.args[0]
    stored = asdict(record)
    for field_name in REQUIRED_LLM_CALL_FIELDS:
        assert field_name in stored
    assert stored["job_id"] == job_id
    assert stored["opportunity_id"] == opportunity_id
    assert stored["provider"] == "anthropic"
    assert stored["status"] == "success"
    assert stored["input_tokens"] == 100
    assert stored["output_tokens"] == 50
    assert stored["total_tokens"] == 150


def test_llm_call_survives_restart() -> None:
    from app.services.data.memory_store import MemoryDataStore

    job_id = uuid.uuid4()
    store = MemoryDataStore()
    store.append_llm_call(
        {
            "request_id": uuid.uuid4(),
            "job_id": job_id,
            "opportunity_id": uuid.uuid4(),
            "stage": "framework",
            "provider": "anthropic",
            "model": "claude-sonnet-4",
            "prompt_version": "synthesis_v1",
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "latency_ms": 12,
            "retry_count": 0,
            "status": "success",
            "estimated_cost_eur": 0.001,
        }
    )
    reset_llm_call_logs()
    snapshot = store.llm_calls
    revived = MemoryDataStore(llm_calls=snapshot)
    found = revived.get_llm_calls_for_job(str(job_id))
    assert len(found) == 1
    assert found[0]["input_tokens"] == 10
    assert get_llm_call_logs() == []


def test_no_confidential_content_in_llm_record() -> None:
    from app.services.data.memory_store import MemoryDataStore
    from services.observability.llm_logger import llm_observability_scope

    store = MemoryDataStore()
    job_id = uuid.uuid4()
    with llm_observability_scope(job_id=job_id, opportunity_id=uuid.uuid4(), store=store):
        invoke_llm(
            stage=LlmStage.PLANNING,
            model="gpt-4.1-mini",
            prompt_version="presentation_planner_v1",
            retry_count=0,
            call=lambda: {
                "prompt": "secret",
                "messages": [{"content": "confidential transcript"}],
                "body": "do not persist",
            },
            input_tokens=lambda _: 8,
            output_tokens=lambda _: 4,
        )

    record = store.get_llm_calls_for_job(str(job_id))[0]
    for forbidden in ("prompt", "messages", "content", "transcript", "body"):
        assert forbidden not in record


def test_each_pipeline_stage_persists_to_store() -> None:
    from app.services.data.memory_store import MemoryDataStore
    from services.observability.llm_logger import llm_observability_scope

    store = MemoryDataStore()
    job_id = uuid.uuid4()
    opportunity_id = uuid.uuid4()
    stages = (
        (LlmStage.FRAMEWORK, "claude-sonnet-4", "synthesis_v1"),
        (LlmStage.PLANNING, "gpt-4.1-mini", "presentation_planner_v1"),
        (LlmStage.SLIDE_GENERATION, "gpt-4.1-mini", "context_01_v1"),
        (LlmStage.COMPRESSION, "gpt-4.1-mini", "compression_v1"),
    )
    with llm_observability_scope(job_id=job_id, opportunity_id=opportunity_id, store=store):
        for index, (stage, model, prompt_version) in enumerate(stages):
            invoke_llm(
                stage=stage,
                model=model,
                prompt_version=prompt_version,
                retry_count=index,
                call=lambda: {"ok": True},
                input_tokens=lambda _: 10 + index,
                output_tokens=lambda _: 5 + index,
            )

    rows = store.get_llm_calls_for_job(str(job_id))
    assert {row["stage"] for row in rows} == {stage.value for stage, _, _ in stages}
    by_stage = {row["stage"]: row for row in rows}
    assert by_stage["framework"]["retry_count"] == 0
    assert by_stage["compression"]["retry_count"] == 3
    assert by_stage["planning"]["prompt_version"] == "presentation_planner_v1"
    assert by_stage["slide_generation"]["total_tokens"] == 10 + 5 + 2 + 2


def test_retry_count_is_persisted_on_durable_record() -> None:
    from unittest.mock import MagicMock

    from services.observability.llm_logger import llm_observability_scope

    store = MagicMock()
    with llm_observability_scope(job_id=uuid.uuid4(), opportunity_id=uuid.uuid4(), store=store):
        invoke_llm(
            stage=LlmStage.FRAMEWORK,
            model="claude-sonnet-4",
            prompt_version="synthesis_v1",
            retry_count=2,
            call=lambda: {"ok": True},
            input_tokens=lambda _: 11,
            output_tokens=lambda _: 7,
        )

    record = store.append_llm_call.call_args.args[0]
    assert asdict(record)["retry_count"] == 2


def test_job_metrics_aggregated_after_completion() -> None:
    from app.schemas.jobs import JobStage
    from app.services import job_service
    from app.services.data.memory_store import MemoryDataStore
    from app.services.job_service import JobStore
    from services.observability.llm_logger import llm_observability_scope

    store = MemoryDataStore()
    original = job_service.job_store
    job_service.job_store = JobStore()
    try:
        job = job_service.create_job(uuid.uuid4(), "framework_generation", repository=store)
        job_service.advance_stage(
            job.id,
            JobStage.FRAMEWORK_VALIDATING,
            repository=store,
        )
        with llm_observability_scope(
            job_id=job.id,
            opportunity_id=job.opportunity_id,
            store=store,
        ):
            for tokens in ((100, 20), (200, 40), (50, 10)):
                invoke_llm(
                    stage=LlmStage.FRAMEWORK,
                    model="claude-sonnet-4",
                    prompt_version="synthesis_v1",
                    retry_count=0,
                    call=lambda pair=tokens: pair,
                    input_tokens=lambda pair: pair[0],
                    output_tokens=lambda pair: pair[1],
                )
        completed = job_service.complete_job(job.id, repository=store)
        assert completed.number_of_ai_calls == 3
        assert completed.ai_input_tokens == 350
        assert completed.ai_output_tokens == 70
        assert completed.llm_cost_eur > 0
        row = store.get_generation_job(job.id)
        assert row is not None
        assert row["number_of_ai_calls"] == 3
        assert row["ai_input_tokens"] == 350
        assert row["ai_output_tokens"] == 70
        assert float(row["llm_cost_eur"]) == completed.llm_cost_eur
    finally:
        job_service.job_store = original
