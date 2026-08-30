"""Job enqueue and status routes (AT-36 / AT-45)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.config import settings
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.jobs import JobEnqueueResponse, JobResponse
from app.services import job_service
from app.services.api_errors import not_found
from app.worker import health_check_task

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/health-check", response_model=JobEnqueueResponse)
def enqueue_health_check() -> JobEnqueueResponse:
    """Enqueue wiring test task — dev-only proof of Celery + Redis."""
    async_result = health_check_task.delay()
    return JobEnqueueResponse(job_id=async_result.id, status="queued")


@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str, user: AuthUserDep, store: DataStoreDep) -> JobResponse:
    """Return generation job stage state (v2 §24)."""
    try:
        parsed_id = UUID(job_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": f"No job found with id {job_id}",
            },
        ) from exc

    job = job_service.get_job(parsed_id, repository=store)
    if job is None and settings.API_DATA_BACKEND == "memory":
        job = job_service.get_job(parsed_id)
    if job is None:
        raise not_found("JOB_NOT_FOUND", f"No job found with id {job_id}")

    store.get_opportunity(opportunity_id=job.opportunity_id, user_id=user.id)
    return job_service.job_to_response(job)
