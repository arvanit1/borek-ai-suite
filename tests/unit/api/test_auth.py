"""AT-39: Supabase JWT authentication unit tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import AuthUser, create_test_access_token, decode_access_token, get_current_user
from app.config import settings
from app.main import create_app

USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER_EMAIL = "user-a@example.com"


def test_get_current_user_raises_401_without_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "UNAUTHORIZED"


def test_get_current_user_raises_401_with_invalid_jwt() -> None:
    from fastapi.security import HTTPAuthorizationCredentials

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials)

    assert exc_info.value.status_code == 401


def test_get_current_user_raises_401_with_expired_jwt() -> None:
    from fastapi.security import HTTPAuthorizationCredentials

    token = create_test_access_token(
        user_id=USER_ID,
        email=USER_EMAIL,
        secret=settings.SUPABASE_JWT_SECRET,
        expired=True,
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials)

    assert exc_info.value.status_code == 401


def test_get_current_user_returns_auth_user_for_valid_jwt() -> None:
    from fastapi.security import HTTPAuthorizationCredentials

    token = create_test_access_token(
        user_id=USER_ID,
        email=USER_EMAIL,
        secret=settings.SUPABASE_JWT_SECRET,
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = get_current_user(credentials)

    assert isinstance(user, AuthUser)
    assert user.id == USER_ID
    assert user.email == USER_EMAIL


def test_decode_access_token_returns_auth_user() -> None:
    token = create_test_access_token(
        user_id=USER_ID,
        email=USER_EMAIL,
        secret=settings.SUPABASE_JWT_SECRET,
    )
    user = decode_access_token(token)
    assert user.id == USER_ID
    assert user.email == USER_EMAIL


def test_protected_router_returns_401_without_token() -> None:
    client = TestClient(create_app())
    response = client.get("/jobs/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_health_returns_200_without_token() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
