"""AT-57: re-dispatch a resumed generation job from its stored enqueue payload."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.job_service import Job, JobNotRetryableError


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
