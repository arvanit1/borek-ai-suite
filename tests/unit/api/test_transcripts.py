"""AT-40: transcript endpoint unit tests."""

from __future__ import annotations

import io
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


def test_upload_list_and_get_transcript() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    upload = client.post(
        f"/opportunities/{opportunity_id}/transcripts",
        headers=_headers(),
        files={"file": ("meeting.txt", io.BytesIO(b"hello transcript"), "text/plain")},
    )
    assert upload.status_code == 201
    transcript_id = upload.json()["transcript"]["id"]
    assert upload.json()["processing_status"] == "pending"

    listed = client.get(f"/opportunities/{opportunity_id}/transcripts", headers=_headers())
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    detail = client.get(
        f"/opportunities/{opportunity_id}/transcripts/{transcript_id}",
        headers=_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["file_name"] == "meeting.txt"
    source = get_memory_store().list_transcript_sources(
        opportunity_id=uuid.UUID(opportunity_id),
        user_id=USER_ID,
    )[0]
    assert source["conversation_id"] == "C1"
    assert source["sections"][0]["content"] == "hello transcript"


def test_upload_rejects_invalid_extension() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    response = client.post(
        f"/opportunities/{opportunity_id}/transcripts",
        headers=_headers(),
        files={"file": ("notes.pdf", io.BytesIO(b"pdf"), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_TRANSCRIPT_FORMAT"


def test_upload_assigns_stable_conversation_ids_per_opportunity() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)

    for name in ("first.txt", "second.txt"):
        response = client.post(
            f"/opportunities/{opportunity_id}/transcripts",
            headers=_headers(),
            files={"file": (name, io.BytesIO(b"Alex: Valid transcript"), "text/plain")},
        )
        assert response.status_code == 201

    sources = get_memory_store().list_transcript_sources(
        opportunity_id=uuid.UUID(opportunity_id),
        user_id=USER_ID,
    )
    assert [source["conversation_id"] for source in sources] == ["C1", "C2"]


def test_regenerate_transcript_resets_processing_status() -> None:
    client = _client()
    opportunity_id = _create_opportunity(client)
    upload = client.post(
        f"/opportunities/{opportunity_id}/transcripts",
        headers=_headers(),
        files={
            "file": (
                "meeting.vtt",
                io.BytesIO(b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nAlex: Hello"),
                "text/vtt",
            )
        },
    )
    transcript_id = upload.json()["transcript"]["id"]

    response = client.post(
        f"/opportunities/{opportunity_id}/transcripts/{transcript_id}/regenerate",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["processing_status"] == "pending"
