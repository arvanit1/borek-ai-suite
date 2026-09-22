"""BT-34 opportunity API, persistence adapters, validation and dependency boundary."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services.data.supabase_store import SupabaseDataStore
from app.services.stage1 import get_company_research_provider
from services.framework.stage1_research import CompanyEvidence

OWNER = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
INTAKE = {
    "client_website": "https://example.com",
    "poc_name": "Ada Lovelace",
    "poc_position": "Operations",
    "sales_topic_description": "Invoice matching",
    "about_company": "Sales says the client has 500 employees.",
}


def headers(owner: UUID = OWNER) -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + create_test_access_token(
            user_id=owner,
            email="sales@example.com",
            secret=settings.SUPABASE_JWT_SECRET,
        )
    }


def create(client: TestClient, **extra: object) -> dict:
    response = client.post(
        "/opportunities",
        headers=headers(),
        json={
            "client_name": "Acme",
            "opportunity_name": "Automation",
            "department": "Sales",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_intake_create_get_list_patch_and_clear():
    with TestClient(create_app()) as client:
        row = create(client, stage1_intake=INTAKE)
        path = f"/opportunities/{row['id']}"
        assert row["stage1_intake"] == INTAKE
        assert client.get(path, headers=headers()).json()["stage1_intake"] == INTAKE
        assert (
            client.get("/opportunities", headers=headers()).json()[0]["stage1_intake"]
            == INTAKE
        )
        unrelated = client.patch(
            path, headers=headers(), json={"department": "Finance"}
        ).json()
        assert unrelated["stage1_intake"] == INTAKE
        replacement = client.patch(
            path,
            headers=headers(),
            json={"stage1_intake": {"about_company": "Updated"}},
        )
        assert replacement.status_code == 200
        assert replacement.json()["stage1_intake"]["about_company"] == "Updated"
        assert replacement.json()["stage1_intake"]["client_website"] is None
        assert (
            client.patch(path, headers=headers(), json={"stage1_intake": None}).json()[
                "stage1_intake"
            ]
            is None
        )
        assert client.get(path, headers=headers()).json()["stage1_intake"] is None


@pytest.mark.parametrize("intake", [None, {}, {"about_company": "", "poc_name": "   "}])
def test_optional_intake_and_old_clients(intake):
    with TestClient(create_app()) as client:
        legacy = create(client)
        assert legacy["stage1_intake"] is None
        row = create(client, stage1_intake=intake)
        if row["stage1_intake"]:
            assert all(value is None for value in row["stage1_intake"].values())


@pytest.mark.parametrize(
    "intake",
    [
        {"client_website": "javascript:alert(1)"},
        {"client_website": "https://user:pass@example.com"},
        {"client_website": "example.com"},
        {"client_website": "https://example.com:bad"},
        {"client_website": "https://example.com/\nsecret"},
        *[{field: "bad\x00text"} for field in INTAKE],
        {"poc_name": 123},
        {"poc_position": "x" * 201},
        {"sales_topic_description": "x" * 20_001},
        {"voice_transcript": "speaker: text"},
        {"transcript": "speaker: text"},
    ],
)
def test_invalid_intake_on_create_and_update(intake):
    with TestClient(create_app()) as client:
        base = {
            "client_name": "Acme",
            "opportunity_name": "Automation",
            "department": "Sales",
        }
        assert (
            client.post(
                "/opportunities",
                headers=headers(),
                json={**base, "stage1_intake": intake},
            ).status_code
            == 422
        )
        row = create(client, stage1_intake=INTAKE)
        path = f"/opportunities/{row['id']}"
        assert (
            client.patch(
                path, headers=headers(), json={"stage1_intake": intake}
            ).status_code
            == 422
        )
        assert client.get(path, headers=headers()).json()["stage1_intake"] == INTAKE


def test_voice_empty_and_unavailable_preserve_topic_and_auth():
    with TestClient(create_app()) as client:
        row = create(client, stage1_intake=INTAKE)
        path = f"/opportunities/{row['id']}/stage1-voice"
        assert client.post(path, headers=headers()).json() == {
            "status": "not_provided",
            "transcript": None,
        }
        assert (
            client.post(
                path,
                headers=headers(),
                files={"file": ("empty.webm", b"", "audio/webm")},
            ).status_code
            == 200
        )
        response = client.post(
            path,
            headers=headers(),
            files={"file": ("voice.webm", b"audio", "audio/webm")},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "STAGE1_VOICE_UNAVAILABLE"
        assert (
            client.get(f"/opportunities/{row['id']}", headers=headers()).json()[
                "stage1_intake"
            ]
            == INTAKE
        )
        assert client.post(path, headers=headers(uuid4())).status_code == 404
        assert client.post(path).status_code == 401


def test_research_missing_provider_and_ownership():
    with TestClient(create_app()) as client:
        row = create(client, stage1_intake=INTAKE)
        path = f"/opportunities/{row['id']}/stage1-research"
        response = client.post(path, headers=headers())
        assert response.status_code == 200, response.text
        result = response.json()
        assert "COMPANY_RESEARCH_PROVIDER_UNAVAILABLE" in result["dependencies"]
        assert all(fact["value"] is None for fact in result["company_facts"].values())
        assert (
            result["user_statements"]["fields"]["about_company"]
            == INTAKE["about_company"]
        )
        assert client.post(path, headers=headers(uuid4())).status_code == 404
        assert client.post(path).status_code == 401


def test_research_provider_dependency_is_wired_and_errors_are_safe():
    class Provider:
        def research(self, **kwargs):
            assert kwargs == {
                "client_name": "Acme",
                "client_website": "https://example.com",
            }
            return [
                CompanyEvidence(
                    "headquarters", "Berlin", "report", "page:2", "HQ: Berlin"
                )
            ]

    app = create_app()
    app.dependency_overrides[get_company_research_provider] = lambda: Provider()
    with TestClient(app) as client:
        row = create(client, stage1_intake=INTAKE)
        path = f"/opportunities/{row['id']}/stage1-research"
        assert (
            client.post(path, headers=headers()).json()["company_facts"][
                "headquarters"
            ]["value"]
            == "Berlin"
        )

        class BrokenProvider:
            def research(self, **kwargs):
                raise RuntimeError("secret client source text")

        app.dependency_overrides[get_company_research_provider] = (
            lambda: BrokenProvider()
        )
        response = client.post(path, headers=headers())
        assert response.status_code == 502
        assert "secret client" not in response.text


def test_supabase_adapter_roundtrip_including_null_and_owner_filter(monkeypatch):
    """Exercise production adapter serialization against a fake REST transport."""
    db = {}

    def request(self, method, table, *, json_body=None, params=None):
        assert table == "opportunities"
        if method == "POST":
            db.update(copy.deepcopy(json_body))
            db.update(
                id=str(uuid4()),
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )
        else:
            assert params["created_by"] == f"eq.{OWNER}"
            if method == "PATCH":
                db.update(copy.deepcopy(json_body))
        return httpx.Response(
            201 if method == "POST" else 200, json=[copy.deepcopy(db)]
        )

    monkeypatch.setattr(SupabaseDataStore, "_request", request)
    store = SupabaseDataStore("test-token")
    row = store.create_opportunity(
        user_id=OWNER,
        client_name="Acme",
        opportunity_name="Automation",
        department="Sales",
        language="en",
        stage1_intake=INTAKE,
    )
    second_store = SupabaseDataStore("test-token")
    assert (
        second_store.get_opportunity(opportunity_id=row["id"], user_id=OWNER)[
            "stage1_intake"
        ]
        == INTAKE
    )
    assert second_store.list_opportunities(user_id=OWNER)[0]["stage1_intake"] == INTAKE
    second_store.update_opportunity(
        opportunity_id=row["id"], user_id=OWNER, updates={"department": "Finance"}
    )
    assert db["stage1_intake"] == INTAKE
    second_store.update_opportunity(
        opportunity_id=row["id"],
        user_id=OWNER,
        updates={"stage1_intake": {"about_company": "Replacement"}},
    )
    assert db["stage1_intake"] == {"about_company": "Replacement"}
    second_store.update_opportunity(
        opportunity_id=row["id"], user_id=OWNER, updates={"stage1_intake": None}
    )
    assert (
        second_store.get_opportunity(opportunity_id=row["id"], user_id=OWNER)[
            "stage1_intake"
        ]
        is None
    )

    del db["stage1_intake"]
    assert (
        second_store.get_opportunity(opportunity_id=row["id"], user_id=OWNER)[
            "stage1_intake"
        ]
        is None
    )
