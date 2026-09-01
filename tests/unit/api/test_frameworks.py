"""AT-41: framework endpoint unit tests."""

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


def _set_latest_framework_status(opportunity_id: str, status: str) -> None:
    store = get_memory_store()
    for row in store.framework_versions.values():
        if str(row["opportunity_id"]) == opportunity_id:
            row["status"] = status
            row["framework_json"]["status"] = status


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
    job = client.get(f"/jobs/{response.json()['job_id']}", headers=_headers())
    assert job.status_code == 200
    assert job.json()["status"] == "COMPLETED"


def test_update_framework_persists_edits() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    framework_json["title"] = "Updated framework title"
    framework_json["chapters"][1]["body"] = [
        {"summary": "Edited management summary with traceable facts."}
    ]

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200
    assert patch.json()["framework_json"]["title"] == "Updated framework title"

    reloaded = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert reloaded.json()["framework_json"]["title"] == "Updated framework title"


def test_review_actions_allow_in_review_and_lock_after_confirm() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    _set_latest_framework_status(opportunity_id, "in_review")

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert latest.json()["status"] == "in_review"
    framework_json = latest.json()["framework_json"]
    framework_json["title"] = "Reviewed in-review title"

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200
    assert patch.json()["framework_json"]["title"] == "Reviewed in-review title"

    regenerate = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    assert regenerate.status_code == 202

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    blocked_regenerate = client.post(
        f"/opportunities/{opportunity_id}/framework/regenerate-chapter",
        headers=_headers(),
        json={"chapter_id": "3"},
    )
    assert blocked_regenerate.status_code == 409
    assert blocked_regenerate.json()["error"]["code"] == "FRAMEWORK_IMMUTABLE"


def test_update_framework_rejects_confirmed_version() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    confirmed = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    framework_json["title"] = "Should not save"

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 409
    assert patch.json()["error"]["code"] == "FRAMEWORK_IMMUTABLE"


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

    confirmed = client.post(
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

    pdf = client.get(
        f"/frameworks/{confirmed.json()['id']}/render?format=pdf",
        headers=_headers(),
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")


def test_confirm_framework_blocks_es13_chapter6_contradiction() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    latest = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    framework_json = latest.json()["framework_json"]
    chapter_6 = next(ch for ch in framework_json["chapters"] if ch["chapter_id"] == "6")
    ai_split = next(block for block in chapter_6["body"] if block.get("block") == "ai_split")
    ai_split["used_for"] = ["Deciding whether a case matches"]
    ai_split["not_used_for"] = ["Deciding whether a case matches", "Evaluating employees"]

    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200

    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 422
    assert confirm.json()["error"]["code"] == "PRE_CONFIRM_FAILED"
    assert "contradicts" in confirm.json()["error"]["message"].lower()

    reloaded = client.get(f"/opportunities/{opportunity_id}/framework", headers=_headers())
    assert reloaded.json()["status"] == "draft"


def test_framework_review_returns_summary_and_attention_signals() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())

    review = client.get(f"/opportunities/{opportunity_id}/framework/review", headers=_headers())
    assert review.status_code == 200
    body = review.json()
    assert body["review_summary"]["headline"]
    assert isinstance(body["attention_signals"], list)
    assert body["review_state"]
    assert body["pii_handling"]["applied_before_llm"] is True
    assert "prompt_observability" in body
