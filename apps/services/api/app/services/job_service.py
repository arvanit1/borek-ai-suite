"""Generation job state machine service (AT-36) — no Celery imports."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

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
    result_json: dict[str, Any] = field(default_factory=dict)
    ai_input_tokens: int = 0
    ai_output_tokens: int = 0
    number_of_ai_calls: int = 0
    render_duration_ms: int = 0
    storage_size_bytes: int = 0
    generation_cost_estimate: float = 0


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


def _job_from_row(row: dict[str, Any]) -> Job:
    return Job(
        id=uuid.UUID(str(row["id"])),
        opportunity_id=uuid.UUID(str(row["opportunity_id"])),
        job_type=str(row["job_type"]),
        status=JobStatus(row.get("status", JobStatus.QUEUED.value)),
        current_stage=JobStage(row.get("current_stage", JobStage.QUEUED.value)),
        presentation_id=(
            uuid.UUID(str(row["presentation_id"])) if row.get("presentation_id") else None
        ),
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        failed_stage=JobStage(row["failed_stage"]) if row.get("failed_stage") else None,
        error_retryable=row.get("error_retryable"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        created_at=row.get("created_at") or datetime.now(UTC),
        result_json=dict(row.get("result_json") or {}),
        ai_input_tokens=int(row.get("ai_input_tokens") or 0),
        ai_output_tokens=int(row.get("ai_output_tokens") or 0),
        number_of_ai_calls=int(row.get("number_of_ai_calls") or 0),
        render_duration_ms=int(row.get("render_duration_ms") or 0),
        storage_size_bytes=int(row.get("storage_size_bytes") or 0),
        generation_cost_estimate=float(row.get("generation_cost_estimate") or 0),
    )


def _job_payload(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "opportunity_id": job.opportunity_id,
        "presentation_id": job.presentation_id,
        "job_type": job.job_type,
        "status": job.status.value,
        "current_stage": job.current_stage.value,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "failed_stage": job.failed_stage.value if job.failed_stage else None,
        "error_retryable": job.error_retryable,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "result_json": job.result_json,
        "ai_input_tokens": job.ai_input_tokens,
        "ai_output_tokens": job.ai_output_tokens,
        "number_of_ai_calls": job.number_of_ai_calls,
        "render_duration_ms": job.render_duration_ms,
        "storage_size_bytes": job.storage_size_bytes,
        "generation_cost_estimate": job.generation_cost_estimate,
    }


def _load(job_id: uuid.UUID, repository: Any | None) -> Job | None:
    if repository is None:
        return job_store.get(job_id)
    row = repository.get_generation_job(job_id)
    return _job_from_row(row) if row is not None else None


def _save(job: Job, repository: Any | None, *, create: bool = False) -> Job:
    if repository is None:
        return job_store.save(job)
    payload = _job_payload(job)
    row = (
        repository.create_generation_job(payload)
        if create
        else repository.update_generation_job(job.id, payload)
    )
    return _job_from_row(row)


def reset_job_store() -> None:
    global job_store
    job_store = JobStore()


def _ensure_not_terminal(job: Job) -> None:
    if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
        raise InvalidJobTransitionError(
            f"Job {job.id} is terminal ({job.status.value}) and cannot be advanced",
        )


def create_job(
    opportunity_id: uuid.UUID,
    job_type: str,
    *,
    presentation_id: uuid.UUID | None = None,
    repository: Any | None = None,
) -> Job:
    job = Job(
        id=uuid.uuid4(),
        opportunity_id=opportunity_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        current_stage=JobStage.QUEUED,
        presentation_id=presentation_id,
    )
    return _save(job, repository, create=True)


def advance_stage(
    job_id: uuid.UUID,
    next_stage: JobStage,
    *,
    repository: Any | None = None,
) -> Job:
    job = _load(job_id, repository)
    if job is None:
        raise JobNotFoundError(str(job_id))

    _ensure_not_terminal(job)

    if job.current_stage not in JOB_PIPELINE_STAGES or next_stage not in JOB_PIPELINE_STAGES:
        raise InvalidJobTransitionError(
            f"Job {job_id} cannot advance from stage {job.current_stage.value}",
        )
    current_index = JOB_PIPELINE_STAGES.index(job.current_stage)
    next_index = JOB_PIPELINE_STAGES.index(next_stage)
    if next_index <= current_index:
        raise InvalidJobTransitionError(
            f"Invalid stage transition {job.current_stage.value} -> {next_stage.value}",
        )

    if job.status == JobStatus.QUEUED and next_stage != JobStage.QUEUED:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)

    job.current_stage = next_stage
    return _save(job, repository)


def complete_job(
    job_id: uuid.UUID,
    *,
    repository: Any | None = None,
    result_json: dict[str, Any] | None = None,
) -> Job:
    job = _load(job_id, repository)
    if job is None:
        raise JobNotFoundError(str(job_id))

    _ensure_not_terminal(job)

    if job.current_stage in {JobStage.QUEUED, JobStage.COMPLETED, JobStage.FAILED}:
        raise InvalidJobTransitionError(
            f"Job {job_id} cannot complete from {job.current_stage.value}",
        )

    job.status = JobStatus.COMPLETED
    job.current_stage = JobStage.COMPLETED
    job.completed_at = datetime.now(UTC)
    if result_json is not None:
        job.result_json = dict(result_json)
    return _save(job, repository)


def fail_job(
    job_id: uuid.UUID,
    error_code: str,
    message: str,
    failed_stage: JobStage,
    retryable: bool,
    *,
    repository: Any | None = None,
) -> Job:
    job = _load(job_id, repository)
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
    return _save(job, repository)


def get_job(job_id: uuid.UUID, *, repository: Any | None = None) -> Job | None:
    return _load(job_id, repository)


def record_metrics(
    job_id: uuid.UUID,
    *,
    repository: Any | None = None,
    render_duration_ms: int | None = None,
    storage_size_bytes: int | None = None,
) -> Job:
    job = _load(job_id, repository)
    if job is None:
        raise JobNotFoundError(str(job_id))
    _ensure_not_terminal(job)
    if render_duration_ms is not None:
        job.render_duration_ms = render_duration_ms
    if storage_size_bytes is not None:
        job.storage_size_bytes = storage_size_bytes
    return _save(job, repository)


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
        result=job.result_json,
        metrics={
            "ai_input_tokens": job.ai_input_tokens,
            "ai_output_tokens": job.ai_output_tokens,
            "number_of_ai_calls": job.number_of_ai_calls,
            "render_duration_ms": job.render_duration_ms,
            "storage_size_bytes": job.storage_size_bytes,
            "generation_cost_estimate": job.generation_cost_estimate,
        },
    )
