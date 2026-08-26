"""AT-34: health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_200() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_body() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
