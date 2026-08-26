"""AT-38 / AT-39 / AT-40 / AT-41: protected router wiring unit tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app


def _auth_header(user_id: uuid.UUID | None = None) -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id or uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        email="authed@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def test_opportunities_requires_authentication() -> None:
    client = TestClient(create_app())
    assert client.get("/opportunities").status_code == 401


def test_frameworks_requires_authentication() -> None:
    client = TestClient(create_app())
    framework_id = "00000000-0000-4000-8000-000000000001"
    assert client.get(f"/frameworks/{framework_id}").status_code == 401


def test_protected_routers_allow_authenticated_requests() -> None:
    client = TestClient(create_app())
    headers = _auth_header()

    assert client.get("/opportunities", headers=headers).status_code == 200
    assert client.get("/presentations", headers=headers).status_code == 200


def test_health_router_remains_public() -> None:
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200
