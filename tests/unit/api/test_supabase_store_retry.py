"""Transient Supabase timeouts must retry and not fail enqueue-after-audit."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

from app.services.audit.audit_log import AuditAction, AuditObjectType, record_audit_event
from app.services.data import supabase_store as supabase_store_module


def test_request_with_retry_succeeds_after_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    class FakeClient:
        is_closed = False

        def request(self, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ReadTimeout("timed out")
            return httpx.Response(200, json=[{"ok": True}])

    monkeypatch.setattr(supabase_store_module, "_HTTP_CLIENT", FakeClient())
    monkeypatch.setattr(supabase_store_module.time, "sleep", lambda *_: None)

    response = supabase_store_module._request_with_retry(
        "GET",
        "https://example.supabase.co/rest/v1/audit_log",
        headers={"Authorization": "Bearer x"},
    )
    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_with_retry_raises_503_after_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        is_closed = False

        def request(self, **kwargs):
            raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(supabase_store_module, "_HTTP_CLIENT", FakeClient())
    monkeypatch.setattr(supabase_store_module.time, "sleep", lambda *_: None)

    with pytest.raises(HTTPException) as exc_info:
        supabase_store_module._request_with_retry(
            "POST",
            "https://example.supabase.co/rest/v1/audit_log",
            headers={"Authorization": "Bearer x"},
            json={"action": "framework.generate"},
        )
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "SUPABASE_UNAVAILABLE"


def test_record_audit_event_does_not_raise_when_store_fails() -> None:
    store = MagicMock()
    store.append_audit_log.side_effect = httpx.ReadTimeout("timed out")

    record_audit_event(
        store,
        actor_id=uuid.uuid4(),
        action=AuditAction.FRAMEWORK_GENERATE,
        object_type=AuditObjectType.FRAMEWORK_VERSION,
        object_id=uuid.uuid4(),
    )
    store.append_audit_log.assert_called_once()
