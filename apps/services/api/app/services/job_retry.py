"""AT-57: re-dispatch a resumed generation job from its stored enqueue payload."""

from __future__ import annotations

from typing import Any

from collections.abc import Callable

from app.config import settings
from app.services.job_service import Job, JobNotRetryableError

TRANSIENT_RETRY_BUDGET = 1
_TRANSIENT_CODES = {
    "PROVIDER_TIMEOUT",
    "PROVIDER_UNAVAILABLE",
    "RENDERER_UNAVAILABLE",
    "RENDERER_TIMEOUT",
    "REDIS_UNAVAILABLE",
    "NETWORK_ERROR",
}
_NON_RETRYABLE_CODES = {
    "VALIDATION_FAILED",
    "CONTENT_CONSTRAINT_EXCEEDED",
    "FRAMEWORK_NOT_CONFIRMED",
    "JOB_NOT_RETRYABLE",
}


def is_transient_failure(exc: BaseException) -> bool:
    if getattr(exc, "retryable", None) is False:
        return False
    code = str(getattr(exc, "code", "") or "")
    if code in _NON_RETRYABLE_CODES:
        return False
    if getattr(exc, "transient", False) is True:
        return True
    if code in _TRANSIENT_CODES:
        return True
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return any(
        token in name or token in message
        for token in ("timeout", "timed out", "temporarily", "connection reset", "network")
    )


def run_with_transient_retry(
    operation: Callable[[], Any],
    *,
    budget: int = TRANSIENT_RETRY_BUDGET,
) -> Any:
    """Retry a clearly transient failure within the approved budget, then raise."""
    last_error: BaseException | None = None
    for attempt in range(budget + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt >= budget or not is_transient_failure(exc):
                raise
    assert last_error is not None
    raise last_error


def enqueue_payload(job: Job) -> dict[str, Any]:
    raw = (job.result_json or {}).get("_enqueue")
    return dict(raw) if isinstance(raw, dict) else {}


def _send(task: Any, *args: str) -> None:
    if settings.API_DATA_BACKEND == "memory":
        task.run(*args)
    else:
        task.delay(*args)


def dispatch_resumed_job(job: Job) -> None:
    payload = enqueue_payload(job)
    job_id = str(job.id)
    if job.job_type == "framework_generation":
        from app.worker import run_framework_generation_task

        _send(
            run_framework_generation_task,
            job_id,
            str(job.opportunity_id),
            str(payload["user_id"]),
            str(payload["framework_version_id"]),
        )
        return
    if job.job_type == "framework_regenerate_chapter":
        from app.worker import run_framework_regenerate_chapter_task

        _send(
            run_framework_regenerate_chapter_task,
            job_id,
            str(payload["framework_version_id"]),
            str(payload["chapter_id"]),
        )
        return
    if job.job_type == "framework_render":
        from app.worker import run_framework_render_task

        _send(
            run_framework_render_task,
            job_id,
            str(payload["framework_version_id"]),
            str(payload["user_id"]),
        )
        return
    if job.job_type == "presentation_planning":
        from app.worker import run_presentation_planning_task

        _send(
            run_presentation_planning_task,
            job_id,
            str(payload["framework_version_id"]),
            str(payload["user_id"]),
            str(payload["presentation_plan_id"]),
        )
        return
    if job.job_type == "presentation_generation":
        from app.worker import run_presentation_generation_task

        _send(
            run_presentation_generation_task,
            job_id,
            str(job.presentation_id or payload["presentation_id"]),
            str(payload["user_id"]),
        )
        return
    if job.job_type == "slide_regenerate":
        from app.worker import run_slide_regenerate_task

        _send(
            run_slide_regenerate_task,
            job_id,
            str(job.presentation_id or payload["presentation_id"]),
            str(payload["slide_id"]),
            str(payload["user_id"]),
        )
        return
    if job.job_type == "slide_change_layout":
        from app.worker import run_slide_change_layout_task

        _send(
            run_slide_change_layout_task,
            job_id,
            str(job.presentation_id or payload["presentation_id"]),
            str(payload["slide_id"]),
            str(payload["user_id"]),
            str(payload["layout_id"]),
        )
        return
    raise JobNotRetryableError(f"Job type {job.job_type} cannot be retried")
