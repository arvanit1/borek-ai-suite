from __future__ import annotations

import copy
import uuid

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services.data.memory_store import get_memory_store
from services.borek_rag.corpus import bundled_corpus_mapping


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def test_retrieval_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/knowledge/retrieve",
            json={"query_key": "pricing:invoice_3way_match:senior_consultant:day_rate"},
        )

    assert response.status_code == 401


def test_retrieval_returns_versioned_price_source() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/knowledge/retrieve",
            headers=_headers(),
            json={
                "kind": "pricing",
                "query_key": "pricing:invoice_3way_match:senior_consultant:day_rate",
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered"
    assert body["payload"]["amount"] == "1250.00"
    assert body["payload"]["indicative"] is True
    assert body["sources"][0]["corpus_version"] == "2026.09.03"
    assert body["sources"][0]["document_version"] == "2026.Q3.1"
    assert body["sources"][0]["fact_id"].startswith("price.")


def test_retrieval_covers_service_staffing_and_reference_kinds() -> None:
    lookups = (
        (
            "service",
            "service:invoice_3way_match:definition",
            "invoice_3way_match",
        ),
        (
            "staffing",
            "staffing:invoice_3way_match:core_team",
            4,
        ),
        (
            "reference",
            "reference:invoice_3way_match:delivery_pattern",
            "structured_finance_operations",
        ),
    )
    with TestClient(create_app()) as client:
        for kind, query_key, expected in lookups:
            response = client.post(
                "/knowledge/retrieve",
                headers=_headers(),
                json={"kind": kind, "query_key": query_key},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["status"] == "answered"
            assert body["sources"][0]["corpus_version"] == "2026.09.03"
            if kind == "service":
                assert body["payload"]["service_key"] == expected
            elif kind == "staffing":
                assert body["payload"]["headcount"] == expected
            else:
                assert body["payload"]["pattern"] == expected


def test_unsupported_fact_returns_unknown_without_content() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/knowledge/retrieve",
            headers=_headers(),
            json={"text": "What is Borek's binding fixed price for a Mars office?"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "unknown",
        "statement": None,
        "payload": None,
        "sources": [],
        "reason": "no_supported_fact",
    }


def test_corpus_endpoint_reports_bundled_dummy_until_ingest() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/knowledge/corpus", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "bundled_dummy"
    assert body["owner"] == "Commercial"
    assert body["version"] == "2026.09.03"
    assert set(body["fact_kinds"]) == {"pricing", "staffing", "service", "reference"}


def test_ingest_is_idempotent_and_switches_retrieval_to_store() -> None:
    custom = copy.deepcopy(bundled_corpus_mapping())
    custom["corpus_version"] = "2026.09.03-store"
    custom["documents"][0]["facts"][0]["payload"]["amount"] = "1325.00"
    custom["documents"][0]["facts"][0]["statement"] = (
        "Senior Consultant day rate for Invoice 3-way Match is EUR 1325.00 "
        "(indicative dummy rate)."
    )

    with TestClient(create_app()) as client:
        first = client.post(
            "/knowledge/ingest",
            headers=_headers(),
            json={"corpus": custom},
        )
        assert first.status_code == 200, first.text
        assert first.json()["source"] == "store"
        assert first.json()["version"] == "2026.09.03-store"
        assert first.json()["replaced_existing"] is False
        assert first.json()["fact_count"] == 4

        second = client.post(
            "/knowledge/ingest",
            headers=_headers(),
            json={"corpus": custom},
        )
        assert second.status_code == 200
        assert second.json()["replaced_existing"] is True
        assert second.json()["version"] == "2026.09.03-store"

        meta = client.get("/knowledge/corpus", headers=_headers())
        assert meta.status_code == 200
        assert meta.json()["source"] == "store"
        assert meta.json()["version"] == "2026.09.03-store"

        retrieved = client.post(
            "/knowledge/retrieve",
            headers=_headers(),
            json={
                "kind": "pricing",
                "query_key": "pricing:invoice_3way_match:senior_consultant:day_rate",
            },
        )
        assert retrieved.status_code == 200
        body = retrieved.json()
        assert body["status"] == "answered"
        assert body["payload"]["amount"] == "1325.00"
        assert body["sources"][0]["corpus_version"] == "2026.09.03-store"
        assert body["sources"][0]["document_type"] == "rate_card"


def test_ingest_retires_previous_approved_version() -> None:
    first = copy.deepcopy(bundled_corpus_mapping())
    first["corpus_version"] = "2026.09.03-a"
    first["documents"][0]["facts"][0]["payload"]["amount"] = "1111.00"
    second = copy.deepcopy(bundled_corpus_mapping())
    second["corpus_version"] = "2026.09.03-b"
    second["documents"][0]["facts"][0]["payload"]["amount"] = "2222.00"

    with TestClient(create_app()) as client:
        assert client.post(
            "/knowledge/ingest",
            headers=_headers(),
            json={"corpus": first},
        ).status_code == 200
        assert client.post(
            "/knowledge/ingest",
            headers=_headers(),
            json={"corpus": second},
        ).status_code == 200
        statuses = {
            row["version"]: row["status"]
            for row in get_memory_store().knowledge_corpus_versions.values()
        }
        assert statuses == {"2026.09.03-a": "retired", "2026.09.03-b": "approved"}
        retrieved = client.post(
            "/knowledge/retrieve",
            headers=_headers(),
            json={
                "kind": "pricing",
                "query_key": "pricing:invoice_3way_match:senior_consultant:day_rate",
            },
        )
        assert retrieved.status_code == 200
        assert retrieved.json()["payload"]["amount"] == "2222.00"
        assert retrieved.json()["sources"][0]["corpus_version"] == "2026.09.03-b"


def test_ingest_rejects_unstructured_pricing() -> None:
    invalid = copy.deepcopy(bundled_corpus_mapping())
    invalid["documents"][0]["facts"][0]["payload"] = {"notes": "about twelve hundred"}

    with TestClient(create_app()) as client:
        response = client.post(
            "/knowledge/ingest",
            headers=_headers(),
            json={"corpus": invalid},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_KNOWLEDGE_CORPUS"
    assert "structured rate-card" in response.json()["error"]["message"]


def test_ingest_rejects_non_commercial_owner() -> None:
    invalid = copy.deepcopy(bundled_corpus_mapping())
    invalid["owner"] = "The model"

    with TestClient(create_app()) as client:
        response = client.post(
            "/knowledge/ingest",
            headers=_headers(),
            json={"corpus": invalid},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_KNOWLEDGE_CORPUS"


def test_ingest_is_forbidden_on_supabase_backend(monkeypatch) -> None:
    monkeypatch.setattr(settings, "API_DATA_BACKEND", "supabase")
    with TestClient(create_app()) as client:
        response = client.post("/knowledge/ingest", headers=_headers(), json={})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "KNOWLEDGE_INGEST_FORBIDDEN"
