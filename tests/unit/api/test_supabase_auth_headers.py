"""Supabase credential compatibility for user JWTs and privileged server keys."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest
from fastapi import HTTPException

from app.config import settings
from app.services.data import supabase_store as supabase_store_module
from app.services.data.supabase_store import SupabaseDataStore


ANON_KEY = "test-public-anon-key"
USER_JWT = "test-user-access-jwt"
LEGACY_SERVICE_ROLE = "test-legacy-service-role-jwt"
SECRET_KEY = "sb_secret_test_backend_key"


def _set_credentials(
    monkeypatch: pytest.MonkeyPatch,
    *,
    service_credential: str,
) -> None:
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", ANON_KEY)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", service_credential)


def test_user_jwt_uses_anon_apikey_and_bearer_user_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_credentials(monkeypatch, service_credential=LEGACY_SERVICE_ROLE)

    store = SupabaseDataStore(USER_JWT)

    assert store._headers["apikey"] == ANON_KEY
    assert store._headers["Authorization"] == f"Bearer {USER_JWT}"


def test_legacy_service_role_uses_service_apikey_and_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_credentials(monkeypatch, service_credential=LEGACY_SERVICE_ROLE)

    store = SupabaseDataStore(LEGACY_SERVICE_ROLE)

    assert store._headers["apikey"] == LEGACY_SERVICE_ROLE
    assert store._headers["Authorization"] == f"Bearer {LEGACY_SERVICE_ROLE}"


def test_secret_key_uses_apikey_without_bearer_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_credentials(monkeypatch, service_credential=SECRET_KEY)

    store = SupabaseDataStore(SECRET_KEY)

    assert store._headers["apikey"] == SECRET_KEY
    assert "Authorization" not in store._headers


@pytest.mark.parametrize(
    ("service_credential", "access_token", "expected_apikey", "expected_authorization"),
    [
        (LEGACY_SERVICE_ROLE, USER_JWT, ANON_KEY, f"Bearer {USER_JWT}"),
        (
            LEGACY_SERVICE_ROLE,
            LEGACY_SERVICE_ROLE,
            LEGACY_SERVICE_ROLE,
            f"Bearer {LEGACY_SERVICE_ROLE}",
        ),
        (SECRET_KEY, SECRET_KEY, SECRET_KEY, None),
    ],
)
def test_storage_upload_and_delete_use_the_same_auth_semantics(
    monkeypatch: pytest.MonkeyPatch,
    service_credential: str,
    access_token: str,
    expected_apikey: str,
    expected_authorization: str | None,
) -> None:
    _set_credentials(monkeypatch, service_credential=service_credential)
    captured: list[dict[str, Any]] = []

    def request_with_retry(method: str, url: str, **kwargs: Any) -> httpx.Response:
        captured.append({"method": method, "url": url, **kwargs})
        return httpx.Response(201 if method == "POST" else 204)

    monkeypatch.setattr(
        supabase_store_module,
        "_request_with_retry",
        request_with_retry,
    )
    store = SupabaseDataStore(access_token)

    store._upload_transcript_content(
        storage_path="owner/transcript.txt",
        mime_type="text/plain",
        content=b"content",
    )
    store._delete_transcript_content(storage_path="owner/transcript.txt")

    assert [call["method"] for call in captured] == ["POST", "DELETE"]
    for call in captured:
        headers = call["headers"]
        assert headers["apikey"] == expected_apikey
        if expected_authorization is None:
            assert "Authorization" not in headers
        else:
            assert headers["Authorization"] == expected_authorization


def test_secret_key_is_not_exposed_in_storage_errors_or_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _set_credentials(monkeypatch, service_credential=SECRET_KEY)
    responses = iter(
        (
            httpx.Response(400, text="storage rejected the request"),
            httpx.Response(500, text="storage cleanup failed"),
        )
    )
    monkeypatch.setattr(
        supabase_store_module,
        "_request_with_retry",
        lambda *args, **kwargs: next(responses),
    )
    store = SupabaseDataStore(SECRET_KEY)

    with pytest.raises(HTTPException) as exc_info:
        store._upload_transcript_content(
            storage_path="owner/transcript.txt",
            mime_type="text/plain",
            content=b"content",
        )
    with caplog.at_level(logging.WARNING):
        store._delete_transcript_content(storage_path="owner/transcript.txt")

    assert SECRET_KEY not in str(exc_info.value.detail)
    assert SECRET_KEY not in caplog.text
