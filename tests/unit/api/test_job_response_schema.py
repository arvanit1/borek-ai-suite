"""AT-36: JobResponse schema serialization tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.schemas.jobs import JobErrorDetail, JobResponse, JobStage, JobStatus
from app.services import job_service
from app.services.job_service import JobStore


def test_job_response_without_error_serializes_correctly() -> None:
    response = JobResponse(
        job_id=str(uuid.uuid4()),
        job_type="framework_generation",
        status=JobStatus.RUNNING,
        current_stage=JobStage.TRANSCRIPT_PROCESSING,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=None,
        error=None,
    )

    payload = response.model_dump(mode="json")
    assert payload["error"] is None
    assert payload["status"] == "RUNNING"
    assert payload["current_stage"] == "TRANSCRIPT_PROCESSING"


def test_job_response_with_error_serializes_correctly() -> None:
    response = JobResponse(
        job_id=str(uuid.uuid4()),
        job_type="presentation_generation",
        status=JobStatus.FAILED,
        current_stage=JobStage.FAILED,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 2, tzinfo=UTC),
        error=JobErrorDetail(
            code="PPTX_RENDER_FAILED",
            message="Renderer unavailable",
            stage=JobStage.PPTX_RENDERING,
            retryable=True,
        ),
    )

    payload = response.model_dump(mode="json")
    assert payload["error"]["code"] == "PPTX_RENDER_FAILED"
    assert payload["error"]["stage"] == "PPTX_RENDERING"
    assert payload["error"]["retryable"] is True


def test_error_field_absent_when_status_not_failed() -> None:
    original = job_service.job_store
    job_service.job_store = JobStore()
    try:
        job = job_service.create_job(uuid.uuid4(), "framework_generation")
        response = job_service.job_to_response(job)
        assert response.status != JobStatus.FAILED
        assert response.error is None
    finally:
        job_service.job_store = original
