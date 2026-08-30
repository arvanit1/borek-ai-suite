"""AT-44: slide regenerate and change-layout endpoint tests."""

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


def _create_presentation_with_slides(client: TestClient) -> tuple[str, str]:
    opportunity = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
        },
    )
    assert opportunity.status_code == 201
    opportunity_id = opportunity.json()["id"]

    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    generated = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={},
    )
    assert generated.status_code == 202
    presentation_id = generated.json()["presentation_id"]

    slides = client.get(f"/presentations/{presentation_id}/slides", headers=_headers())
    assert slides.status_code == 200
    assert len(slides.json()) >= 1
    return presentation_id, slides.json()[0]["id"]


def test_regenerate_slide_enqueues_job() -> None:
    client = _client()
    presentation_id, slide_id = _create_presentation_with_slides(client)

    response = client.post(
        f"/presentations/{presentation_id}/slides/{slide_id}/regenerate",
        headers=_headers(),
    )
    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    assert body["status"] == "queued"


def test_change_layout_enqueues_job_and_creates_new_version() -> None:
    client = _client()
    presentation_id, slide_id = _create_presentation_with_slides(client)

    response = client.post(
        f"/presentations/{presentation_id}/slides/{slide_id}/change-layout",
        headers=_headers(),
        json={"layout_id": "COVER_01"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    assert body["status"] == "queued"

    job = client.get(f"/jobs/{body['job_id']}", headers=_headers()).json()
    assert job["status"] == "COMPLETED"
    new_slide_id = job["result"]["slide_id"]
    assert new_slide_id != slide_id

    slide = client.get(
        f"/presentations/{presentation_id}/slides/{new_slide_id}",
        headers=_headers(),
    )
    assert slide.status_code == 200
    assert slide.json()["layout_id"] == "COVER_01"


def test_change_layout_rejects_different_category() -> None:
    client = _client()
    presentation_id, slide_id = _create_presentation_with_slides(client)

    response = client.post(
        f"/presentations/{presentation_id}/slides/{slide_id}/change-layout",
        headers=_headers(),
        json={"layout_id": "CONTEXT_01"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LAYOUT_CATEGORY_MISMATCH"


def test_change_layout_rejects_unknown_layout_id() -> None:
    client = _client()
    presentation_id, slide_id = _create_presentation_with_slides(client)

    response = client.post(
        f"/presentations/{presentation_id}/slides/{slide_id}/change-layout",
        headers=_headers(),
        json={"layout_id": "NOT_A_LAYOUT"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_LAYOUT_ID"
