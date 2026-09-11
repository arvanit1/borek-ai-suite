"""MS-24: recent-work summary is one request and stays user-scoped."""

from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OTHER_USER = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


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
            "language": "en",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_recent_work_empty_for_new_user() -> None:
    client = _client()
    response = client.get("/opportunities/recent-work", headers=_headers(OTHER_USER))
    assert response.status_code == 200
    assert response.json() == []


def test_recent_work_summarizes_owned_opportunities() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    upload = client.post(
        f"/opportunities/{opportunity_id}/transcripts",
        headers=_headers(),
        files={"file": ("meeting.txt", io.BytesIO(b"Alex: hello transcript"), "text/plain")},
    )
    assert upload.status_code == 201

    response = client.get("/opportunities/recent-work", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    snapshot = body[0]
    assert snapshot["opportunity"]["id"] == opportunity_id
    assert snapshot["opportunity"]["created_by"] == str(USER_ID)
    assert snapshot["transcript_count"] == 1
    assert snapshot["has_plan"] is False
    assert snapshot["presentation_id"] is None
    assert snapshot["resource_load_failed"] is False

    other = client.get("/opportunities/recent-work", headers=_headers(OTHER_USER))
    assert other.status_code == 200
    assert other.json() == []
