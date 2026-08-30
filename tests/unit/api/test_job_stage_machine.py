"""AT-36: job stage state machine unit tests."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.jobs import JOB_PIPELINE_STAGES, JobResponse, JobStage, JobStatus
from app.services import job_service
from app.services.job_service import InvalidJobTransitionError, JobStore
from app.services.data.memory_store import MemoryDataStore


@pytest.fixture(autouse=True)
def isolated_job_store() -> None:
    original = job_service.job_store
    job_service.job_store = JobStore()
    yield
    job_service.job_store = original


def test_job_stage_enum_values_in_order() -> None:
    expected = [
        "QUEUED",
        "TRANSCRIPT_PROCESSING",
        "KNOWLEDGE_EXTRACTING",
        "FRAMEWORK_SYNTHESIZING",
        "FRAMEWORK_VALIDATING",
        "PRESENTATION_PLANNING",
        "SLIDE_GENERATING",
        "SLIDE_VALIDATING",
        "PPTX_RENDERING",
        "PREVIEW_RENDERING",
        "COMPLETED",
        "FAILED",
    ]
    assert [stage.value for stage in JobStage] == expected
    assert len(JobStage) == 12
    assert list(JOB_PIPELINE_STAGES) == [JobStage.QUEUED, *expected[1:10]]


def test_job_status_enum_has_four_values() -> None:
    assert {status.value for status in JobStatus} == {
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
    }


def test_advance_stage_allows_job_specific_forward_stages() -> None:
    job = job_service.create_job(uuid.uuid4(), "framework_generation")

    advanced = job_service.advance_stage(job.id, JobStage.KNOWLEDGE_EXTRACTING)

    assert advanced.current_stage == JobStage.KNOWLEDGE_EXTRACTING


def test_advance_stage_rejects_going_backward() -> None:
    job = job_service.create_job(uuid.uuid4(), "framework_generation")
    job_service.advance_stage(job.id, JobStage.TRANSCRIPT_PROCESSING)

    with pytest.raises(InvalidJobTransitionError):
        job_service.advance_stage(job.id, JobStage.QUEUED)


def test_advance_stage_rejects_from_completed() -> None:
    job = _job_at_preview_rendering()

    job_service.complete_job(job.id)

    with pytest.raises(InvalidJobTransitionError):
        job_service.advance_stage(job.id, JobStage.COMPLETED)


def test_advance_stage_rejects_from_failed() -> None:
    job = job_service.create_job(uuid.uuid4(), "framework_generation")
    job_service.fail_job(
        job.id,
        "RENDER_ERROR",
        "Preview failed",
        JobStage.TRANSCRIPT_PROCESSING,
        True,
    )

    with pytest.raises(InvalidJobTransitionError):
        job_service.advance_stage(job.id, JobStage.KNOWLEDGE_EXTRACTING)


def test_complete_job_accepts_job_specific_terminal_stage() -> None:
    job = job_service.create_job(uuid.uuid4(), "framework_generation")
    job_service.advance_stage(job.id, JobStage.FRAMEWORK_VALIDATING)

    completed = job_service.complete_job(job.id)

    assert completed.current_stage == JobStage.COMPLETED


def test_fail_job_accepted_from_non_terminal_stage() -> None:
    job = job_service.create_job(uuid.uuid4(), "framework_generation")
    job_service.advance_stage(job.id, JobStage.TRANSCRIPT_PROCESSING)

    failed = job_service.fail_job(
        job.id,
        "EXTRACTION_FAILED",
        "Transcript parse error",
        JobStage.TRANSCRIPT_PROCESSING,
        True,
    )

    assert failed.status == JobStatus.FAILED
    assert failed.current_stage == JobStage.FAILED


def test_failed_job_response_includes_error_fields() -> None:
    job = job_service.create_job(uuid.uuid4(), "framework_generation")
    job_service.advance_stage(job.id, JobStage.TRANSCRIPT_PROCESSING)
    job_service.fail_job(
        job.id,
        "EXTRACTION_FAILED",
        "Transcript parse error",
        JobStage.TRANSCRIPT_PROCESSING,
        True,
    )

    response = job_service.job_to_response(job_service.get_job(job.id))
    assert response is not None
    assert response.error is not None
    assert response.error.stage == JobStage.TRANSCRIPT_PROCESSING
    assert response.error.retryable is True


def test_job_response_serializes_to_expected_json_shape() -> None:
    job = _job_at_preview_rendering()
    completed = job_service.complete_job(job.id)
    response = job_service.job_to_response(completed)

    payload = response.model_dump(mode="json")
    assert payload["job_id"] == str(completed.id)
    assert payload["job_type"] == "framework_generation"
    assert payload["status"] == "COMPLETED"
    assert payload["current_stage"] == "COMPLETED"
    assert "started_at" in payload
    assert "completed_at" in payload
    assert payload["error"] is None


def test_job_state_persists_in_data_store_repository() -> None:
    repository = MemoryDataStore()
    opportunity_id = uuid.uuid4()
    created = job_service.create_job(
        opportunity_id,
        "presentation_planning",
        repository=repository,
    )

    advanced = job_service.advance_stage(
        created.id,
        JobStage.PRESENTATION_PLANNING,
        repository=repository,
    )
    completed = job_service.complete_job(
        created.id,
        repository=repository,
        result_json={"presentation_plan_id": str(uuid.uuid4())},
    )

    assert advanced.status == JobStatus.RUNNING
    assert job_service.get_job(created.id, repository=repository) == completed


def _job_at_preview_rendering():
    job = job_service.create_job(uuid.uuid4(), "framework_generation")
    for stage in JOB_PIPELINE_STAGES[1:]:
        job = job_service.advance_stage(job.id, stage)
    assert job.current_stage == JobStage.PREVIEW_RENDERING
    return job
