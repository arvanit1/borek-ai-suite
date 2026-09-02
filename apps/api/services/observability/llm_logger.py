"""Shared LLM observability — AT-53 call metadata and ES-32 generation-job logs."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Iterator, TypeVar
from uuid import uuid4

T = TypeVar("T")
logger = logging.getLogger(__name__)

_llm_job_id: ContextVar[uuid.UUID | None] = ContextVar("at53_llm_job_id", default=None)
_llm_opportunity_id: ContextVar[uuid.UUID | None] = ContextVar("at53_llm_opportunity_id", default=None)
_llm_store: ContextVar[Any | None] = ContextVar("at53_llm_store", default=None)

# Approximate EUR per 1M tokens. Metadata only — not billing.
_EUR_PER_1M: dict[str, tuple[float, float]] = {
    "claude": (2.80, 14.00),
    "gpt-4.1-mini": (0.37, 1.48),
    "gpt-4.1": (1.84, 7.36),
    "gpt-4o-mini": (0.14, 0.55),
    "gpt-4o": (2.30, 9.20),
}

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
    job_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None
    provider: str = "unknown"
    status: str = "success"
    error_category: str | None = None
    estimated_cost_eur: float = 0.0

    def to_json_dict(self) -> dict[str, Any]:
        """JSON-safe metadata for job result_json and API responses (AT-53)."""
        return {
            "request_id": str(self.request_id),
            "stage": self.stage,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "job_id": str(self.job_id) if self.job_id is not None else None,
            "opportunity_id": str(self.opportunity_id) if self.opportunity_id is not None else None,
            "provider": self.provider,
            "status": self.status,
            "error_category": self.error_category,
            "estimated_cost_eur": self.estimated_cost_eur,
        }


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


def _optional_uuid(value: Any) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def infer_provider(model: str) -> str:
    name = (model or "").lower()
    if "claude" in name or "anthropic" in name:
        return "anthropic"
    if any(token in name for token in ("gpt", "o1", "o3", "o4", "openai")):
        return "openai"
    return "unknown"


def estimate_cost_eur(*, model: str, input_tokens: int, output_tokens: int) -> float:
    name = (model or "").lower()
    rates = _EUR_PER_1M["claude"] if "claude" in name else None
    if rates is None:
        for key, value in _EUR_PER_1M.items():
            if key in name:
                rates = value
                break
    if rates is None:
        rates = (1.00, 4.00)
    input_rate, output_rate = rates
    return round(
        (max(input_tokens, 0) * input_rate + max(output_tokens, 0) * output_rate) / 1_000_000,
        6,
    )


@contextmanager
def llm_observability_scope(
    *,
    job_id: uuid.UUID | str | None = None,
    opportunity_id: uuid.UUID | str | None = None,
    store: Any | None = None,
) -> Iterator[None]:
    """Bind job/opportunity/store for all invoke_llm calls in this worker task."""
    tokens: list[tuple[ContextVar[Any], Any]] = []
    if job_id is not None:
        tokens.append((_llm_job_id, _llm_job_id.set(_optional_uuid(job_id))))
    if opportunity_id is not None:
        tokens.append((_llm_opportunity_id, _llm_opportunity_id.set(_optional_uuid(opportunity_id))))
    if store is not None:
        tokens.append((_llm_store, _llm_store.set(store)))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def _reject_confidential_fields(extra_fields: dict[str, object]) -> None:
    forbidden = FORBIDDEN_LOG_FIELD_NAMES.intersection(extra_fields)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise ValueError(f"LLM observability logs must not include confidential fields: {joined}")


def _persist_llm_call(entry: LlmCallRecord) -> None:
    store = _llm_store.get()
    if store is None:
        return
    try:
        store.append_llm_call(entry)
    except Exception:
        logger.warning(
            "Durable LLM call persist failed for request %s job %s",
            entry.request_id,
            entry.job_id,
            exc_info=True,
        )


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
    job_id: uuid.UUID | str | None = None,
    opportunity_id: uuid.UUID | str | None = None,
    provider: str | None = None,
    status: str = "success",
    error_category: str | None = None,
    estimated_cost_eur: float | None = None,
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

    resolved_job_id = _optional_uuid(job_id) or _llm_job_id.get()
    resolved_opportunity_id = _optional_uuid(opportunity_id) or _llm_opportunity_id.get()
    resolved_provider = provider or infer_provider(model)
    resolved_cost = (
        estimated_cost_eur
        if estimated_cost_eur is not None
        else estimate_cost_eur(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )

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
        job_id=resolved_job_id,
        opportunity_id=resolved_opportunity_id,
        provider=resolved_provider,
        status=status,
        error_category=error_category,
        estimated_cost_eur=resolved_cost,
    )
    stored = _llm_call_log_store.append(entry)
    _persist_llm_call(stored)
    return stored


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
    job_id: uuid.UUID | str | None = None,
    opportunity_id: uuid.UUID | str | None = None,
    provider: str | None = None,
) -> T:
    """Execute an LLM-backed call and log request metadata without prompt/response bodies."""
    request_id = uuid.uuid4()
    started = time.perf_counter()
    try:
        result = call()
    except Exception as exc:
        log_llm_call(
            request_id=request_id,
            stage=stage,
            model=model,
            prompt_version=prompt_version,
            input_tokens=0,
            output_tokens=0,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            retry_count=retry_count,
            job_id=job_id,
            opportunity_id=opportunity_id,
            provider=provider,
            status="failed",
            error_category=type(exc).__name__,
        )
        raise
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
        job_id=job_id,
        opportunity_id=opportunity_id,
        provider=provider,
        status="success",
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
        log_llm_call(
            request_id=uuid.uuid4(),
            stage=stage,
            model=model or "unknown",
            prompt_version=prompt_version,
            input_tokens=0,
            output_tokens=0,
            latency_ms=float(latency_ms),
            retry_count=max(attempt - 1, 0),
            opportunity_id=opportunity_id,
            status="failed",
            error_category=type(exc).__name__,
        )
        raise
    usage = usage_out[0] if usage_out else None
    latency_ms = int((time.perf_counter() - started) * 1000)
    input_tokens = _token_count(usage, "input_tokens") or 0
    output_tokens = _token_count(usage, "output_tokens") or 0
    log_generation_job(
        stage=stage,
        prompt_version=prompt_version,
        model=model,
        status="success",
        attempt=attempt,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        opportunity_id=opportunity_id,
        conversation_id=conversation_id,
        framework_id=framework_id,
    )
    log_llm_call(
        request_id=uuid.uuid4(),
        stage=stage,
        model=model or "unknown",
        prompt_version=prompt_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=float(latency_ms),
        retry_count=max(attempt - 1, 0),
        opportunity_id=opportunity_id,
        status="success",
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
