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


class JobNotRetryableError(Exception):
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
    llm_cost_eur: float = 0


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
        llm_cost_eur=float(row.get("llm_cost_eur") or row.get("generation_cost_estimate") or 0),
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
        "llm_cost_eur": job.llm_cost_eur,
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


_TERMINAL_JOB_STATUSES = {JobStatus.COMPLETED.value, JobStatus.FAILED.value}


def job_matches_stage_group(job_type: str, stage_group: str | None) -> bool:
    if not stage_group:
        return True
    name = str(job_type or "").lower()
    if stage_group == "framework":
        return "framework" in name
    if stage_group == "presentation":
        return "presentation" in name or "slide" in name
    return True


def _job_status_value(row: dict[str, Any]) -> str:
    value = row.get("status")
    return value.value if hasattr(value, "value") else str(value or "")


def _job_timestamp(row: dict[str, Any], *keys: str) -> datetime:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return datetime.min.replace(tzinfo=UTC)


def select_reconnect_job(
    rows: list[dict[str, Any]],
    *,
    stage_group: str | None = None,
) -> dict[str, Any] | None:
    matched = [
        row
        for row in rows
        if job_matches_stage_group(str(row.get("job_type") or ""), stage_group)
    ]
    active = [row for row in matched if _job_status_value(row) not in _TERMINAL_JOB_STATUSES]
    if active:
        return max(active, key=lambda row: _job_timestamp(row, "started_at", "created_at"))
    if matched:
        return max(matched, key=lambda row: _job_timestamp(row, "completed_at", "started_at", "created_at"))
    return None


def is_non_terminal_job(row: dict[str, Any] | Job | None) -> bool:
    if row is None:
        return False
    if isinstance(row, Job):
        return row.status not in {JobStatus.COMPLETED, JobStatus.FAILED}
    return _job_status_value(row) not in _TERMINAL_JOB_STATUSES


def reuse_active_generation_job(
    repository: Any,
    opportunity_id: uuid.UUID,
    stage_group: str | None = None,
    *,
    job_type: str | None = None,
) -> Job | None:
    getter = getattr(repository, "get_active_job_for_opportunity", None)
    if getter is None:
        return None
    row = getter(opportunity_id, stage_group, job_type=job_type)
    if row is None or not is_non_terminal_job(row):
        return None
    if job_type is not None and str(row.get("job_type") or "") != job_type:
        return None
    return _job_from_row(row)


def enqueue_status_for_job(job: Job, *, existing: bool) -> str:
    if existing and job.status == JobStatus.RUNNING:
        return "running"
    return "queued"


def create_job(
    opportunity_id: uuid.UUID,
    job_type: str,
    *,
    presentation_id: uuid.UUID | None = None,
    enqueue: dict[str, Any] | None = None,
    repository: Any | None = None,
) -> Job:
    job = Job(
        id=uuid.uuid4(),
        opportunity_id=opportunity_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        current_stage=JobStage.QUEUED,
        presentation_id=presentation_id,
        result_json={"_enqueue": dict(enqueue)} if enqueue else {},
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


def ensure_stage(
    job_id: uuid.UUID,
    stage: JobStage,
    *,
    repository: Any | None = None,
) -> Job:
    """Advance to *stage* or no-op if the job already reached it (AT-57 resume)."""
    job = _load(job_id, repository)
    if job is None:
        raise JobNotFoundError(str(job_id))
    if job.current_stage == stage:
        if job.status == JobStatus.QUEUED and stage != JobStage.QUEUED:
            job.status = JobStatus.RUNNING
            job.started_at = job.started_at or datetime.now(UTC)
            return _save(job, repository)
        return job
    if (
        job.current_stage in JOB_PIPELINE_STAGES
        and stage in JOB_PIPELINE_STAGES
        and JOB_PIPELINE_STAGES.index(stage) < JOB_PIPELINE_STAGES.index(job.current_stage)
    ):
        return job
    return advance_stage(job_id, stage, repository=repository)


def resume_job(
    job_id: uuid.UUID,
    *,
    from_stage: JobStage | None = None,
    repository: Any | None = None,
) -> Job:
    """Reopen a failed retryable job at *from_stage* or the recorded failed_stage."""
    job = _load(job_id, repository)
    if job is None:
        raise JobNotFoundError(str(job_id))
    if job.status != JobStatus.FAILED:
        raise InvalidJobTransitionError(
            f"Job {job_id} cannot be resumed from status {job.status.value}",
        )
    if not job.error_retryable:
        raise JobNotRetryableError(f"Job {job_id} is not retryable")
    stage = from_stage or job.failed_stage
    if stage is None or stage not in JOB_PIPELINE_STAGES:
        raise InvalidJobTransitionError(
            f"Job {job_id} has no pipeline stage to resume from",
        )
    if (
        job.failed_stage is not None
        and job.failed_stage in JOB_PIPELINE_STAGES
        and JOB_PIPELINE_STAGES.index(stage) > JOB_PIPELINE_STAGES.index(job.failed_stage)
    ):
        raise InvalidJobTransitionError(
            f"Job {job_id} cannot resume after failed stage {job.failed_stage.value}",
        )
    job.status = JobStatus.RUNNING
    job.current_stage = stage
    job.completed_at = None
    job.error_code = None
    job.error_message = None
    job.failed_stage = None
    job.error_retryable = None
    if job.started_at is None:
        job.started_at = datetime.now(UTC)
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
        job.result_json = {**job.result_json, **dict(result_json)}
    _apply_llm_job_metrics(job, repository)
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
    _apply_llm_job_metrics(job, repository)
    return _save(job, repository)


def get_job(job_id: uuid.UUID, *, repository: Any | None = None) -> Job | None:
    return _load(job_id, repository)


def get_latest_job_for_opportunity(
    opportunity_id: uuid.UUID,
    *,
    repository: Any,
) -> Job | None:
    row = repository.get_latest_generation_job_for_opportunity(opportunity_id)
    return _job_from_row(row) if row is not None else None


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
        created_at=job.created_at,
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
            "llm_cost_eur": job.llm_cost_eur,
        },
    )


def _apply_llm_job_metrics(job: Job, repository: Any | None) -> None:
    store = repository
    if store is None:
        try:
            from app.services.data.memory_store import get_memory_store

            store = get_memory_store()
        except Exception:
            return
    getter = getattr(store, "get_llm_calls_for_job", None)
    if getter is None:
        return
    try:
        calls = getter(str(job.id))
    except Exception:
        return
    if not calls:
        return
    job.number_of_ai_calls = len(calls)
    job.ai_input_tokens = sum(int(call.get("input_tokens") or 0) for call in calls)
    job.ai_output_tokens = sum(int(call.get("output_tokens") or 0) for call in calls)
    cost = sum(float(call.get("estimated_cost_eur") or 0) for call in calls)
    job.llm_cost_eur = cost
    job.generation_cost_estimate = cost
