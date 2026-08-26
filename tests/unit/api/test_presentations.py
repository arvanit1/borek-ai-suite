"""AT-42 / AT-43: presentation plan and presentation generate endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _client() -> TestClient:
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
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


def _confirm_framework(client: TestClient, opportunity_id: str) -> str:
    client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    return confirm.json()["id"]


def test_generate_presentation_plan_requires_confirmed_framework() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    blocked = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "FRAMEWORK_NOT_CONFIRMED"


def test_generate_presentation_plan_enqueues_job_and_persists_plan() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    framework_version_id = _confirm_framework(client, opportunity_id)

    response = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={"framework_version_id": framework_version_id},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert body["presentation_plan_id"]

    latest = client.get(
        f"/opportunities/{opportunity_id}/presentation-plan",
        headers=_headers(),
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == body["presentation_plan_id"]
    assert latest.json()["plan_json"]["slides"]

    by_id = client.get(
        f"/presentation-plans/{body['presentation_plan_id']}",
        headers=_headers(),
    )
    assert by_id.status_code == 200
    assert by_id.json()["framework_version_id"] == framework_version_id


def test_generate_presentation_rejects_non_confirmed_framework() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    blocked = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={},
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "FRAMEWORK_NOT_CONFIRMED"


def test_generate_presentation_requires_plan_then_enqueues_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)

    missing_plan = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={},
    )
    assert missing_plan.status_code == 400
    assert missing_plan.json()["error"]["code"] == "PRESENTATION_PLAN_NOT_FOUND"

    plan = client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    assert plan.status_code == 202
    presentation_plan_id = plan.json()["presentation_plan_id"]

    response = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={"presentation_plan_id": presentation_plan_id},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert body["presentation_id"]
    assert body["presentation_plan_id"] == presentation_plan_id

    listed = client.get("/presentations", headers=_headers())
    assert listed.status_code == 200
    assert any(item["id"] == body["presentation_id"] for item in listed.json())

    fetched = client.get(f"/presentations/{body['presentation_id']}", headers=_headers())
    assert fetched.status_code == 200
    assert fetched.json()["presentation_plan_id"] == presentation_plan_id
