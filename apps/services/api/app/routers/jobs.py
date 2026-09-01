"""Job enqueue, status, and retry routes (AT-36 / AT-45 / AT-57)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.config import settings
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.jobs import JobEnqueueResponse, JobResponse, JobStage
from app.services import job_service
from app.services.api_errors import bad_request, not_found
from app.services.audit import AuditObjectType, record_audit_event
from app.services.job_retry import dispatch_resumed_job
from app.services.job_service import InvalidJobTransitionError, JobNotRetryableError
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


@router.post("/{job_id}/retry", response_model=JobEnqueueResponse, status_code=202)
def retry_job(
    job_id: str,
    user: AuthUserDep,
    store: DataStoreDep,
    from_stage: JobStage | None = None,
) -> JobEnqueueResponse:
    try:
        parsed_id = UUID(job_id)
    except ValueError as exc:
        raise not_found("JOB_NOT_FOUND", f"No job found with id {job_id}") from exc

    job = job_service.get_job(parsed_id, repository=store)
    if job is None and settings.API_DATA_BACKEND == "memory":
        job = job_service.get_job(parsed_id)
    if job is None:
        raise not_found("JOB_NOT_FOUND", f"No job found with id {job_id}")

    store.get_opportunity(opportunity_id=job.opportunity_id, user_id=user.id)
    try:
        resumed = job_service.resume_job(
            parsed_id,
            from_stage=from_stage,
            repository=store,
        )
        dispatch_resumed_job(resumed)
    except JobNotRetryableError as exc:
        raise bad_request("JOB_NOT_RETRYABLE", str(exc)) from exc
    except InvalidJobTransitionError as exc:
        raise bad_request("JOB_RETRY_INVALID", str(exc)) from exc
    except KeyError as exc:
        raise bad_request(
            "JOB_RETRY_UNAVAILABLE",
            f"Job {job_id} is missing enqueue payload key {exc}",
        ) from exc

    record_audit_event(
        store,
        actor_id=user.id,
        action="job.retry",
        object_type=AuditObjectType.OPPORTUNITY,
        object_id=job.opportunity_id,
    )
    return JobEnqueueResponse(
        job_id=str(resumed.id),
        status=job_service.enqueue_status_for_job(resumed, existing=False),
        is_existing_job=False,
    )
