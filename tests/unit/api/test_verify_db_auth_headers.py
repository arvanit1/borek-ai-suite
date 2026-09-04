"""Credential compatibility checks for the Supabase REST verification script."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from scripts import verify_db


LEGACY_SERVICE_ROLE = "test-legacy-service-role-jwt"
SECRET_KEY = "sb_secret_test_verify_db_key"


class _SuccessfulClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __enter__(self) -> _SuccessfulClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        rows = [{"id": "test-id"}] if "id" in (kwargs.get("params") or {}) else []
        return httpx.Response(200, json=rows)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return httpx.Response(201)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"method": "DELETE", "url": url, **kwargs})
        return httpx.Response(204)


@pytest.mark.parametrize(
    ("credential", "expected_authorization"),
    [
        (LEGACY_SERVICE_ROLE, f"Bearer {LEGACY_SERVICE_ROLE}"),
        (SECRET_KEY, None),
    ],
)
def test_verify_via_rest_uses_compatible_privileged_headers_without_logging_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    credential: str,
    expected_authorization: str | None,
) -> None:
    client = _SuccessfulClient()
    monkeypatch.setattr(verify_db.httpx, "Client", lambda **kwargs: client)

    assert verify_db.verify_via_rest("https://example.supabase.co", credential) == 0

    assert client.calls
    for call in client.calls:
        headers = call["headers"]
        assert headers["apikey"] == credential
        if expected_authorization is None:
            assert "Authorization" not in headers
        else:
            assert headers["Authorization"] == expected_authorization
    assert credential not in capsys.readouterr().out
