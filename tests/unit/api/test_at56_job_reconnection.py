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


def _confirm_framework(client: TestClient, opportunity_id: str) -> str:
    generated = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    assert generated.status_code == 202, generated.text
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200, confirm.text
    return confirm.json()["id"]


def test_duplicate_plan_generate_returns_existing_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)
    plan_id = uuid.uuid4()
    job = job_service.create_job(
        uuid.UUID(opportunity_id),
        "presentation_planning",
        enqueue={"presentation_plan_id": str(plan_id), "user_id": str(USER_A)},
        repository=get_memory_store(),
    )
    job = job_service.advance_stage(
        job.id,
        JobStage.TRANSCRIPT_PROCESSING,
        repository=get_memory_store(),
    )

    with patch("app.worker.run_presentation_planning_task") as mocked:
        first = client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=_headers(),
            json={},
        )
        second = client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=_headers(),
            json={},
        )

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["job_id"] == str(job.id)
    assert second.json()["job_id"] == str(job.id)
    assert first.json()["is_existing_job"] is True
    assert second.json()["is_existing_job"] is True
    assert first.json()["status"] == "running"
    assert first.json()["presentation_plan_id"] == str(plan_id)
    mocked.delay.assert_not_called()
    mocked.run.assert_not_called()

    store = get_memory_store()
    planning_jobs = [
        row
        for row in store.generation_jobs.values()
        if str(row.get("job_type") or "") == "presentation_planning"
    ]
    assert len(planning_jobs) == 1


def test_plan_generate_does_not_reuse_running_deck_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)
    deck_job = _create_job(opportunity_id, "presentation_generation")

    with patch("app.worker.run_presentation_planning_task") as mocked:
        response = client.post(
            f"/opportunities/{opportunity_id}/presentation-plan/generate",
            headers=_headers(),
            json={},
        )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["is_existing_job"] is False
    assert body["job_id"] != str(deck_job.id)
    assert body["status"] == "queued"
    mocked.run.assert_called_once()


def test_refresh_during_framework_generation() -> None:
    """PDF AT-56: refresh during Framework resumes the active job."""
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = _create_job(opportunity_id, "framework_generation")

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "framework"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["job_type"] == "framework_generation"
    assert body["status"] == "RUNNING"


def test_refresh_after_completion_returns_completed_job() -> None:
    """PDF AT-56: refresh after completion returns the completed result."""
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = _create_job(opportunity_id, "framework_generation", complete=True)

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "framework"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["status"] == "COMPLETED"
    assert body["current_stage"] == "COMPLETED"


def test_refresh_during_slide_generation() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = _create_job(opportunity_id, "slide_regenerate")

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "presentation"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == str(job.id)
    assert body["job_type"] == "slide_regenerate"
    assert body["status"] == "RUNNING"


def test_failed_job_returned_when_no_active() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    job = _create_job(opportunity_id, "framework_generation")
    failed = job_service.fail_job(
        job.id,
        "FRAMEWORK_GENERATION_FAILED",
        "Synthesis failed",
        JobStage.FRAMEWORK_SYNTHESIZING,
        True,
        repository=get_memory_store(),
    )

    response = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "framework"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == str(failed.id)
    assert body["status"] == "FAILED"
    assert body["error"] is not None
    assert body["error"]["code"] == "FRAMEWORK_GENERATION_FAILED"


def test_multiple_historical_jobs_resolve_to_latest() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    older = _create_job(opportunity_id, "framework_generation", complete=True)
    newer = _create_job(opportunity_id, "framework_generation")

    active = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "framework"},
    )
    assert active.status_code == 200, active.text
    assert active.json()["job_id"] == str(newer.id)
    assert active.json()["status"] == "RUNNING"

    job_service.complete_job(newer.id, repository=get_memory_store())
    completed = client.get(
        f"/opportunities/{opportunity_id}/jobs/active",
        headers=_headers(),
        params={"stage_group": "framework"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["job_id"] == str(newer.id)
    assert completed.json()["job_id"] != str(older.id)
    assert completed.json()["status"] == "COMPLETED"


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
