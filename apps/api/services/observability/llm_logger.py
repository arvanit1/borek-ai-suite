"""Shared LLM observability — AT-53 call metadata and ES-32 generation-job logs."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Generic, TypeVar
from uuid import uuid4

T = TypeVar("T")

FORBIDDEN_LOG_FIELD_NAMES = frozenset(
    {
        "prompt",
        "messages",
        "content",
        "response",
        "response_text",
        "transcript",
        "framework_json",
        "slide_spec",
        "body",
        "input_text",
        "output_text",
        "raw_response",
        "system_prompt",
        "user_prompt",
    }
)


class LlmStage(StrEnum):
    FRAMEWORK = "framework"
    PLANNING = "planning"
    SLIDE_GENERATION = "slide_generation"
    COMPRESSION = "compression"


STAGE_EXTRACTION = "knowledge_extraction"
STAGE_SYNTHESIS = "framework_synthesis"
STAGE_LOCALIZE = "customer_localize"
STAGE_PROCESS_SCOPE = "process_scope"


@dataclass(frozen=True)
class LlmCallRecord:
    request_id: uuid.UUID
    stage: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    retry_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class LlmCallLogStore:
    def __init__(self) -> None:
        self._entries: list[LlmCallRecord] = []

    def append(self, entry: LlmCallRecord) -> LlmCallRecord:
        self._entries.append(entry)
        return entry

    def list_entries(self) -> list[LlmCallRecord]:
        return list(self._entries)


_llm_call_log_store = LlmCallLogStore()
_GENERATION_JOBS: list[dict[str, Any]] = []


def reset_llm_call_logs() -> None:
    global _llm_call_log_store
    _llm_call_log_store = LlmCallLogStore()


def get_llm_call_logs() -> list[LlmCallRecord]:
    return _llm_call_log_store.list_entries()


def clear_generation_jobs() -> None:
    """Test helper for ES-32 generation-job logs."""
    _GENERATION_JOBS.clear()


def _reject_confidential_fields(extra_fields: dict[str, object]) -> None:
    forbidden = FORBIDDEN_LOG_FIELD_NAMES.intersection(extra_fields)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise ValueError(f"LLM observability logs must not include confidential fields: {joined}")


def log_llm_call(
    *,
    request_id: uuid.UUID,
    stage: LlmStage | str,
    model: str,
    prompt_version: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    retry_count: int,
    timestamp: datetime | None = None,
    **extra_fields: object,
) -> LlmCallRecord:
    """Persist one LLM call metadata record. Confidential payload fields are rejected."""
    _reject_confidential_fields(extra_fields)
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    if retry_count < 0:
        raise ValueError("retry_count must be non-negative")
    if latency_ms < 0:
        raise ValueError("latency_ms must be non-negative")

    entry = LlmCallRecord(
        request_id=request_id,
        stage=str(stage),
        model=model,
        prompt_version=prompt_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        latency_ms=latency_ms,
        retry_count=retry_count,
        timestamp=timestamp or datetime.now(UTC),
    )
    return _llm_call_log_store.append(entry)


def log_generation_job(
    *,
    stage: str,
    prompt_version: str,
    model: str | None,
    status: str,
    attempt: int = 1,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    opportunity_id: str | None = None,
    conversation_id: str | None = None,
    framework_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Append one ES-32 generation-job log row."""
    entry = {
        "request_id": f"gen-{uuid4()}",
        "stage": stage,
        "prompt_version": prompt_version,
        "model": model,
        "status": status,
        "attempt": attempt,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "opportunity_id": opportunity_id,
        "conversation_id": conversation_id,
        "framework_id": framework_id,
        "error": error,
        "logged_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    _GENERATION_JOBS.append(entry)
    return entry


def jobs_for_opportunity(
    opportunity_id: str,
    *,
    stages: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    items = [
        item
        for item in _GENERATION_JOBS
        if item.get("opportunity_id") == opportunity_id
        and (stages is None or item.get("stage") in stages)
    ]
    if limit is not None:
        return items[-limit:]
    return list(items)


def invoke_llm(
    *,
    stage: LlmStage | str,
    model: str,
    prompt_version: str,
    retry_count: int,
    call: Callable[[], T],
    input_tokens: Callable[[T], int] | None = None,
    output_tokens: Callable[[T], int] | None = None,
) -> T:
    """Execute an LLM-backed call and log request metadata without prompt/response bodies."""
    request_id = uuid.uuid4()
    started = time.perf_counter()
    result = call()
    latency_ms = (time.perf_counter() - started) * 1000.0

    resolved_input_tokens = input_tokens(result) if input_tokens else 0
    resolved_output_tokens = output_tokens(result) if output_tokens else 0

    log_llm_call(
        request_id=request_id,
        stage=stage,
        model=model,
        prompt_version=prompt_version,
        input_tokens=resolved_input_tokens,
        output_tokens=resolved_output_tokens,
        latency_ms=latency_ms,
        retry_count=retry_count,
    )
    return result


def run_logged_llm_call(
    *,
    stage: str,
    prompt_version: str,
    model: str | None,
    attempt: int,
    opportunity_id: str | None = None,
    conversation_id: str | None = None,
    framework_id: str | None = None,
    usage_out: list[Any] | None = None,
    invoke: Callable[[], Any],
) -> Any:
    """Execute an LLM call and append a generation-job log row (ES-32)."""
    started = time.perf_counter()
    try:
        payload = invoke()
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log_generation_job(
            stage=stage,
            prompt_version=prompt_version,
            model=model,
            status="failed",
            attempt=attempt,
            latency_ms=latency_ms,
            opportunity_id=opportunity_id,
            conversation_id=conversation_id,
            framework_id=framework_id,
            error=str(exc),
        )
        raise
    usage = usage_out[0] if usage_out else None
    latency_ms = int((time.perf_counter() - started) * 1000)
    log_generation_job(
        stage=stage,
        prompt_version=prompt_version,
        model=model,
        status="success",
        attempt=attempt,
        latency_ms=latency_ms,
        input_tokens=_token_count(usage, "input_tokens"),
        output_tokens=_token_count(usage, "output_tokens"),
        opportunity_id=opportunity_id,
        conversation_id=conversation_id,
        framework_id=framework_id,
    )
    return payload


def _token_count(usage: Any, field: str) -> int | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        value = usage.get(field)
    else:
        value = getattr(usage, field, None)
    return int(value) if isinstance(value, int) else None
