"""Generation job state machine service (AT-36) — no Celery imports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schemas.jobs import (
    JOB_PIPELINE_STAGES,
    JobErrorDetail,
    JobResponse,
    JobStage,
    JobStatus,
)


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Job not found: {job_id}")


class InvalidJobTransitionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass
class Job:
    id: uuid.UUID
    opportunity_id: uuid.UUID
    job_type: str
    status: JobStatus = JobStatus.QUEUED
    current_stage: JobStage = JobStage.QUEUED
    presentation_id: uuid.UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    failed_stage: JobStage | None = None
    error_retryable: bool | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JobStore:
    """In-memory job store — replaced by Postgres session wiring in AT-38+."""

    def __init__(self) -> None:
        self._jobs: dict[uuid.UUID, Job] = {}

    def save(self, job: Job) -> Job:
        self._jobs[job.id] = job
        return job

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self._jobs.get(job_id)


job_store = JobStore()


def reset_job_store() -> None:
    global job_store
    job_store = JobStore()


def _ensure_not_terminal(job: Job) -> None:
    if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
        raise InvalidJobTransitionError(
            f"Job {job.id} is terminal ({job.status.value}) and cannot be advanced",
        )


def _next_pipeline_stage(current: JobStage) -> JobStage | None:
    if current not in JOB_PIPELINE_STAGES:
        return None
    index = JOB_PIPELINE_STAGES.index(current)
    if index >= len(JOB_PIPELINE_STAGES) - 1:
        return None
    return JOB_PIPELINE_STAGES[index + 1]


def create_job(
    opportunity_id: uuid.UUID,
    job_type: str,
    *,
    presentation_id: uuid.UUID | None = None,
) -> Job:
    job = Job(
        id=uuid.uuid4(),
        opportunity_id=opportunity_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        current_stage=JobStage.QUEUED,
        presentation_id=presentation_id,
    )
    return job_store.save(job)


def advance_stage(job_id: uuid.UUID, next_stage: JobStage) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise JobNotFoundError(str(job_id))

    _ensure_not_terminal(job)

    expected_next = _next_pipeline_stage(job.current_stage)
    if expected_next is None:
        raise InvalidJobTransitionError(
            f"Job {job_id} cannot advance from stage {job.current_stage.value}",
        )
    if next_stage != expected_next:
        raise InvalidJobTransitionError(
            f"Invalid stage transition {job.current_stage.value} -> {next_stage.value}; "
            f"expected {expected_next.value}",
        )

    if job.status == JobStatus.QUEUED and next_stage != JobStage.QUEUED:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)

    job.current_stage = next_stage
    return job_store.save(job)


def complete_job(job_id: uuid.UUID) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise JobNotFoundError(str(job_id))

    _ensure_not_terminal(job)

    if job.current_stage != JobStage.PREVIEW_RENDERING:
        raise InvalidJobTransitionError(
            f"Job {job_id} can only complete from PREVIEW_RENDERING; "
            f"current stage is {job.current_stage.value}",
        )

    job.status = JobStatus.COMPLETED
    job.current_stage = JobStage.COMPLETED
    job.completed_at = datetime.now(UTC)
    return job_store.save(job)


def fail_job(
    job_id: uuid.UUID,
    error_code: str,
    message: str,
    failed_stage: JobStage,
    retryable: bool,
) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise JobNotFoundError(str(job_id))

    _ensure_not_terminal(job)

    job.status = JobStatus.FAILED
    job.current_stage = JobStage.FAILED
    job.error_code = error_code
    job.error_message = message
    job.failed_stage = failed_stage
    job.error_retryable = retryable
    job.completed_at = datetime.now(UTC)
    return job_store.save(job)


def get_job(job_id: uuid.UUID) -> Job | None:
    return job_store.get(job_id)


def job_to_response(job: Job) -> JobResponse:
    error: JobErrorDetail | None = None
    if job.status == JobStatus.FAILED and job.failed_stage is not None:
        error = JobErrorDetail(
            code=job.error_code or "JOB_FAILED",
            message=job.error_message or "Job failed",
            stage=job.failed_stage,
            retryable=bool(job.error_retryable),
        )

    return JobResponse(
        job_id=str(job.id),
        job_type=job.job_type,
        status=job.status,
        current_stage=job.current_stage,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=error,
    )
