"""AT-57: retry / resume failed generation jobs."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.schemas.jobs import JobStage, JobStatus
from app.services import job_service
from app.services.data.memory_store import get_memory_store
from app.services.job_service import InvalidJobTransitionError, JobNotRetryableError

USER_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _client() -> TestClient:
    return TestClient(create_app())


def _headers(user_id: uuid.UUID = USER_A, email: str = "owner@example.com") -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id,
        email=email,
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _create_opportunity(client: TestClient) -> str:
    response = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _failed_job(
    opportunity_id: str,
    *,
    retryable: bool = True,
    stage: JobStage = JobStage.FRAMEWORK_SYNTHESIZING,
    enqueue: dict | None = None,
):
    store = get_memory_store()
    job = job_service.create_job(
        uuid.UUID(opportunity_id),
        "framework_generation",
        enqueue=enqueue
        or {
            "user_id": str(USER_A),
            "framework_version_id": str(uuid.uuid4()),
        },
        repository=store,
    )
    job_service.advance_stage(job.id, JobStage.TRANSCRIPT_PROCESSING, repository=store)
    job_service.advance_stage(job.id, JobStage.KNOWLEDGE_EXTRACTING, repository=store)
    job_service.advance_stage(job.id, stage, repository=store)
    return job_service.fail_job(
        job.id,
        "FRAMEWORK_GENERATION_FAILED",
        "Synthesis failed",
        stage,
        retryable,
        repository=store,
    )


def test_resume_job_from_failed_stage() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    failed = _failed_job(opportunity_id)
    store = get_memory_store()

    resumed = job_service.resume_job(failed.id, repository=store)

    assert resumed.status == JobStatus.RUNNING
    assert resumed.current_stage == JobStage.FRAMEWORK_SYNTHESIZING
    assert resumed.error_code is None
    assert resumed.failed_stage is None
    assert resumed.completed_at is None


def test_resume_job_respects_requested_earlier_stage() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    failed = _failed_job(opportunity_id)
    store = get_memory_store()

    resumed = job_service.resume_job(
        failed.id,
        from_stage=JobStage.KNOWLEDGE_EXTRACTING,
        repository=store,
    )
    assert resumed.current_stage == JobStage.KNOWLEDGE_EXTRACTING


def test_resume_rejects_later_than_failed_stage() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    failed = _failed_job(opportunity_id)
    store = get_memory_store()

    with pytest.raises(InvalidJobTransitionError):
        job_service.resume_job(
            failed.id,
            from_stage=JobStage.FRAMEWORK_VALIDATING,
            repository=store,
        )


def test_resume_rejects_non_retryable() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    failed = _failed_job(opportunity_id, retryable=False)
    store = get_memory_store()

    with pytest.raises(JobNotRetryableError):
        job_service.resume_job(failed.id, repository=store)


def test_resume_rejects_completed() -> None:
    store = get_memory_store()
    job = job_service.create_job(uuid.uuid4(), "framework_generation", repository=store)
    job_service.advance_stage(job.id, JobStage.TRANSCRIPT_PROCESSING, repository=store)
    job_service.complete_job(job.id, repository=store)

    with pytest.raises(InvalidJobTransitionError):
        job_service.resume_job(job.id, repository=store)


def test_ensure_stage_skips_already_passed_stages() -> None:
    store = get_memory_store()
    job = job_service.create_job(uuid.uuid4(), "framework_generation", repository=store)
    job_service.advance_stage(job.id, JobStage.TRANSCRIPT_PROCESSING, repository=store)
    job_service.advance_stage(job.id, JobStage.KNOWLEDGE_EXTRACTING, repository=store)
    job_service.advance_stage(job.id, JobStage.FRAMEWORK_SYNTHESIZING, repository=store)

    skipped = job_service.ensure_stage(
        job.id,
        JobStage.TRANSCRIPT_PROCESSING,
        repository=store,
    )
    assert skipped.current_stage == JobStage.FRAMEWORK_SYNTHESIZING

    same = job_service.ensure_stage(
        job.id,
        JobStage.FRAMEWORK_SYNTHESIZING,
        repository=store,
    )
    assert same.current_stage == JobStage.FRAMEWORK_SYNTHESIZING


def test_retry_endpoint_resumes_and_does_not_create_a_new_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    failed = _failed_job(opportunity_id)

    with patch("app.routers.jobs.dispatch_resumed_job") as mocked:
        response = client.post(f"/jobs/{failed.id}/retry", headers=_headers())

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["job_id"] == str(failed.id)
    assert body["is_existing_job"] is False
    mocked.assert_called_once()

    store = get_memory_store()
    framework_jobs = [
        row
        for row in store.generation_jobs.values()
        if str(row.get("job_type")) == "framework_generation"
    ]
    assert len(framework_jobs) == 1
    current = job_service.get_job(failed.id, repository=store)
    assert current is not None
    assert current.status == JobStatus.RUNNING
    assert current.current_stage == JobStage.FRAMEWORK_SYNTHESIZING


def test_retry_non_retryable_returns_400() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    failed = _failed_job(opportunity_id, retryable=False)

    response = client.post(f"/jobs/{failed.id}/retry", headers=_headers())
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "JOB_NOT_RETRYABLE"


def test_wrong_user_cannot_retry_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    failed = _failed_job(opportunity_id)

    response = client.post(
        f"/jobs/{failed.id}/retry",
        headers=_headers(user_id=USER_B, email="other@example.com"),
    )
    assert response.status_code == 404, response.text
