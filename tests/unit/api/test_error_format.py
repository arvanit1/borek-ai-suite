"""AT-34: consistent error response format tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import create_app


class SampleBody(BaseModel):
    name: str


def _client_with_test_routes() -> TestClient:
    app = create_app()

    @app.get("/test/trigger-500")
    def trigger_500() -> None:
        raise RuntimeError("Traceback should not leak to clients")

    @app.post("/test/validate")
    def validate_body(body: SampleBody) -> SampleBody:
        return body

    return TestClient(app, raise_server_exceptions=False)


def test_not_found_uses_standard_error_shape() -> None:
    client = _client_with_test_routes()
    response = client.get("/missing-route")

    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) >= {"code", "message"}
    assert body["error"]["code"] == "NOT_FOUND"


def test_validation_error_uses_standard_error_shape() -> None:
    client = _client_with_test_routes()
    response = client.post("/test/validate", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "detail" in body["error"]
    assert "errors" in body["error"]["detail"]


def test_internal_error_never_exposes_traceback() -> None:
    client = _client_with_test_routes()
    response = client.get("/test/trigger-500")

    assert response.status_code == 500
    text = response.text
    assert "Traceback" not in text
    assert "Traceback should not leak" not in text
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
