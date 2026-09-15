"""MS-32: validated project statics persist on the owner-scoped opportunity."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app

USER_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id,
        email=f"{user_id}@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _statics(*, style: str = "informal") -> dict:
    recipient = {
        "email": "markus@example.com",
        "first_name": "Markus" if style == "informal" else None,
        "last_name": "Weber" if style == "formal" else None,
        "salutation": "Mr" if style == "formal" else None,
        "kind": "to",
        "primary": True,
    }
    return {
        "project_name": "Acme Invoice Pilot",
        "client_short": "Acme",
        "salutation_style": style,
        "standard_recipients": [recipient],
        "sender_profile": {
            "name": "Lena Hoffmann",
            "role": "Project Lead",
            "email": "lena@borek.example",
        },
    }


def _create(client: TestClient, *, followup_statics: dict | None = None) -> dict:
    response = client.post(
        "/opportunities",
        headers=_headers(USER_A),
        json={
            "client_name": "Acme",
            "opportunity_name": "Invoice Pilot",
            "department": "Finance",
            "followup_statics": followup_statics,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_followup_statics_are_optional_and_round_trip() -> None:
    with TestClient(create_app()) as client:
        without = _create(client)
        assert without["followup_statics"] is None

        created = _create(client, followup_statics=_statics())
        assert created["followup_statics"]["project_name"] == "Acme Invoice Pilot"
        loaded = client.get(f"/opportunities/{created['id']}", headers=_headers(USER_A))
        assert loaded.status_code == 200
        assert loaded.json()["followup_statics"] == created["followup_statics"]


def test_followup_statics_patch_formal_and_clear() -> None:
    with TestClient(create_app()) as client:
        created = _create(client, followup_statics=_statics())
        patched = client.patch(
            f"/opportunities/{created['id']}",
            headers=_headers(USER_A),
            json={"followup_statics": _statics(style="formal")},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["followup_statics"]["salutation_style"] == "formal"

        cleared = client.patch(
            f"/opportunities/{created['id']}",
            headers=_headers(USER_A),
            json={"followup_statics": None},
        )
        assert cleared.status_code == 200
        assert cleared.json()["followup_statics"] is None


def test_followup_statics_require_one_usable_primary_recipient() -> None:
    with TestClient(create_app()) as client:
        missing_primary = _statics()
        missing_primary["standard_recipients"][0]["primary"] = False
        response = client.post(
            "/opportunities",
            headers=_headers(USER_A),
            json={
                "client_name": "Acme",
                "opportunity_name": "Invoice Pilot",
                "department": "Finance",
                "followup_statics": missing_primary,
            },
        )
        assert response.status_code == 422

        malformed_email = _statics()
        malformed_email["standard_recipients"][0]["email"] = "not@valid"
        response = client.post(
            "/opportunities",
            headers=_headers(USER_A),
            json={
                "client_name": "Acme",
                "opportunity_name": "Invoice Pilot",
                "department": "Finance",
                "followup_statics": malformed_email,
            },
        )
        assert response.status_code == 422

        formal_without_name = _statics(style="formal")
        formal_without_name["standard_recipients"][0]["last_name"] = None
        response = client.post(
            "/opportunities",
            headers=_headers(USER_A),
            json={
                "client_name": "Acme",
                "opportunity_name": "Invoice Pilot",
                "department": "Finance",
                "followup_statics": formal_without_name,
            },
        )
        assert response.status_code == 422


def test_second_user_cannot_read_or_patch_sender_profile() -> None:
    with TestClient(create_app()) as client:
        created = _create(client, followup_statics=_statics())
        path = f"/opportunities/{created['id']}"
        assert client.get(path, headers=_headers(USER_B)).status_code == 404
        assert client.patch(
            path,
            headers=_headers(USER_B),
            json={"followup_statics": _statics(style="formal")},
        ).status_code == 404
        owned = client.get(path, headers=_headers(USER_A)).json()
        assert owned["followup_statics"]["sender_profile"]["email"] == "lena@borek.example"
