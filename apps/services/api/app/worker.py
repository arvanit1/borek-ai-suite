"""Celery worker application (AT-35)."""

from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "borek_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]


@celery_app.task(name="tasks.health_check")
def health_check_task() -> dict[str, str]:
    """Wiring test task — replaced by real jobs in AT-36+."""
    return {"status": "ok", "worker": "alive"}


@celery_app.task(name="tasks.advance_job_stage")
def advance_job_stage_task(job_id: str, next_stage: str) -> dict[str, str]:
    """Advance a generation job to the next pipeline stage (AT-36)."""
    from uuid import UUID

    from app.schemas.jobs import JobStage
    from app.services import job_service

    job = job_service.advance_stage(UUID(job_id), JobStage(next_stage))
    return {"job_id": str(job.id), "current_stage": job.current_stage.value}
