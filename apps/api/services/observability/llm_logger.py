"""Shared LLM observability logging — metadata only, no confidential content (AT-53)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Callable, Generic, TypeVar

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


def reset_llm_call_logs() -> None:
    global _llm_call_log_store
    _llm_call_log_store = LlmCallLogStore()


def get_llm_call_logs() -> list[LlmCallRecord]:
    return _llm_call_log_store.list_entries()


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
