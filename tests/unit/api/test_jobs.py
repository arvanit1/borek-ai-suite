"""AT-45: job status endpoint HTTP tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.schemas.jobs import JobStage, JobStatus
from app.services import job_service
from app.services.data.memory_store import get_memory_store

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER_USER_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _client() -> TestClient:
    return TestClient(create_app())


def _headers(user_id: uuid.UUID = USER_ID) -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id,
        email="owner@example.com",
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
    assert response.status_code == 201
    return response.json()["id"]


def test_get_job_status_after_framework_generate() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    generate = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    assert generate.status_code == 202
    job_id = generate.json()["job_id"]

    status = client.get(f"/jobs/{job_id}", headers=_headers())
    assert status.status_code == 200
    body = status.json()
    assert body["job_id"] == job_id
    assert body["job_type"] == "framework_generation"
    assert body["status"] == JobStatus.COMPLETED.value
    assert body["current_stage"] == JobStage.COMPLETED.value
    assert body["result"]["framework_version_id"] == generate.json()["framework_version_id"]
    assert body["error"] is None


def test_get_job_status_returns_structured_error_on_failure() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = job_service.create_job(uuid.UUID(opportunity_id), "presentation_generation")
    job_service.fail_job(
        job.id,
        "PPTX_RENDER_FAILED",
        "Renderer unavailable",
        JobStage.PPTX_RENDERING,
        retryable=True,
    )

    status = client.get(f"/jobs/{job.id}", headers=_headers())
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == JobStatus.FAILED.value
    assert body["current_stage"] == JobStage.FAILED.value
    assert body["error"]["code"] == "PPTX_RENDER_FAILED"
    assert body["error"]["stage"] == JobStage.PPTX_RENDERING.value
    assert body["error"]["retryable"] is True


def test_get_job_status_not_found() -> None:
    client = _client()
    missing_id = "00000000-0000-4000-8000-000000000001"
    response = client.get(f"/jobs/{missing_id}", headers=_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_get_job_status_requires_opportunity_ownership() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = job_service.create_job(uuid.UUID(opportunity_id), "framework_generation")

    response = client.get(f"/jobs/{job.id}", headers=_headers(OTHER_USER_ID))
    assert response.status_code == 404


def test_get_latest_opportunity_job_returns_latest_failure() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    store = get_memory_store()
    job_service.create_job(
        uuid.UUID(opportunity_id),
        "framework_generation",
        repository=store,
    )
    latest = job_service.create_job(
        uuid.UUID(opportunity_id),
        "presentation_generation",
        repository=store,
    )
    job_service.fail_job(
        latest.id,
        "PPTX_RENDER_FAILED",
        "Renderer unavailable",
        JobStage.PPTX_RENDERING,
        retryable=True,
        repository=store,
    )

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/latest",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == str(latest.id)
    assert response.json()["status"] == JobStatus.FAILED.value
    assert response.json()["created_at"] is not None


def test_get_latest_opportunity_job_returns_null_without_jobs() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/latest",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json() is None
