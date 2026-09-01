"""AT-56: durable active-job reconnection."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.schemas.jobs import JobStage
from app.services import job_service
from app.services.data.memory_store import get_memory_store

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


def _create_opportunity(client: TestClient, *, user_id: uuid.UUID = USER_A) -> str:
    response = client.post(
        "/opportunities",
        headers=_headers(user_id=user_id),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_job(
    opportunity_id: str,
    job_type: str,
    *,
    complete: bool = False,
):
    store = get_memory_store()
    job = job_service.create_job(
        uuid.UUID(opportunity_id),
        job_type,
        repository=store,
    )
    job = job_service.advance_stage(
        job.id,
        JobStage.TRANSCRIPT_PROCESSING,
        repository=store,
    )
    if complete:
        job = job_service.complete_job(job.id, repository=store)
    return job


def test_active_job_found_during_generation() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = _create_job(opportunity_id, "framework_generation")

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["job_type"] == "framework_generation"
    assert body["status"] == "RUNNING"
    assert body["current_stage"] == "TRANSCRIPT_PROCESSING"
    assert body["started_at"]
    assert body["error"] is None


def test_no_active_job_returns_404() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "ACTIVE_JOB_NOT_FOUND"


def test_completed_job_returned_when_no_active() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = _create_job(opportunity_id, "framework_generation", complete=True)

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["status"] == "COMPLETED"
    assert body["current_stage"] == "COMPLETED"
    assert body["error"] is None


def test_duplicate_generate_returns_existing_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = _create_job(opportunity_id, "framework_generation")

    with patch("app.worker.run_framework_generation_task") as mocked:
        response = client.post(
            f"/opportunities/{opportunity_id}/framework/generate",
            headers=_headers(),
        )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["is_existing_job"] is True
    assert body["status"] == "running"
    mocked.delay.assert_not_called()
    mocked.run.assert_not_called()

    store = get_memory_store()
    framework_jobs = [
        row
        for row in store.generation_jobs.values()
        if "framework" in str(row.get("job_type") or "")
    ]
    assert len(framework_jobs) == 1


def test_wrong_user_cannot_see_active_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client, user_id=USER_A)
    _create_job(opportunity_id, "framework_generation")

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(user_id=USER_B, email="other@example.com"),
    )
    assert response.status_code == 404, response.text


def test_stage_group_filters_correctly() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    framework_job = _create_job(opportunity_id, "framework_generation")
    presentation_job = _create_job(opportunity_id, "presentation_generation")

    framework = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "framework"},
    )
    assert framework.status_code == 200, framework.text
    assert framework.json()["job_id"] == str(framework_job.id)
    assert framework.json()["job_type"] == "framework_generation"

    presentation = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "presentation"},
    )
    assert presentation.status_code == 200, presentation.text
    assert presentation.json()["job_id"] == str(presentation_job.id)
    assert presentation.json()["job_type"] == "presentation_generation"
