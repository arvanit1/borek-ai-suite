"""AT-41: framework endpoint unit tests."""

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


def test_generate_get_and_confirm_framework() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    generate = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    assert generate.status_code == 202
    body = generate.json()
    assert body["status"] == "queued"
    assert body["framework_version_id"]
    assert body["job_id"]

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert latest.status_code == 200
    framework_version_id = latest.json()["id"]
    assert latest.json()["status"] == "draft"

    by_id = client.get(f"/frameworks/{framework_version_id}", headers=_headers())
    assert by_id.status_code == 200

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"


def test_regenerate_chapter_enqueues_job() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    response = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    assert response.status_code == 202
    assert response.json()["job_id"]


def test_render_requires_confirmed_framework() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    blocked = client.post(
        f"/opportunities/{opportunity_id}/framework/render",
        headers=_headers(),
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "FRAMEWORK_NOT_CONFIRMED"

    client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    allowed = client.post(
        f"/opportunities/{opportunity_id}/framework/render",
        headers=_headers(),
    )
    assert allowed.status_code == 202
    assert allowed.json()["job_id"]
