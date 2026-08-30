"""AT-42 / AT-43: presentation plan and presentation generate endpoint tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services.data.memory_store import get_memory_store

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

    version = get_memory_store().get_latest_presentation_version(
        presentation_id=uuid.UUID(body["presentation_id"]),
        user_id=USER_ID,
    )
    cover = next(spec for spec in version["slides_json"] if spec["layoutId"] == "COVER_01")
    assert cover.get("statBadges")
    process = next(spec for spec in version["slides_json"] if spec["layoutId"] == "PROCESS_FLOW_01")
    assert process["sourceChapterIds"] == ["2", "4"]
    assert process.get("phases")
    timeline = next(spec for spec in version["slides_json"] if spec["layoutId"] == "TIMELINE_01")
    assert timeline["sourceChapterIds"] == ["10"]
    assert timeline.get("phases")
    assert timeline.get("milestones")


def _create_presentation(client: TestClient, opportunity_id: str) -> str:
    client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    response = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={},
    )
    assert response.status_code == 202
    return response.json()["presentation_id"]


def test_deck_center_preview_and_downloads() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    _confirm_framework(client, opportunity_id)
    presentation_id = _create_presentation(client, opportunity_id)

    latest = client.get(
        f"/opportunities/{opportunity_id}/presentation",
        headers=_headers(),
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == presentation_id

    deck = client.get(f"/presentations/{presentation_id}/deck", headers=_headers())
    assert deck.status_code == 200
    body = deck.json()
    assert body["presentation_id"] == presentation_id
    assert len(body["slides"]) >= 1
    assert body["slides"][0]["preview_url"].endswith(".png")
    assert body["pptx_download_url"].endswith("/download/pptx")
    assert body["pdf_download_url"].endswith("/download/pdf")

    preview = client.get(
        f"/presentations/{presentation_id}/preview/slides/0.png",
        headers=_headers(),
    )
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/png")

    pptx = client.get(
        f"/presentations/{presentation_id}/download/pptx",
        headers=_headers(),
    )
    assert pptx.status_code == 200
    assert len(pptx.content) > 0

    pdf = client.get(
        f"/presentations/{presentation_id}/download/pdf",
        headers=_headers(),
    )
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
