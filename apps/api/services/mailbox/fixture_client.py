"""Deterministic fixture mailbox client — no real Outlook/Graph calls."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from services.mailbox.contract import MailboxDraftRequest, MailboxDraftResult
from services.mailbox.errors import (
    MailboxClientRecipientForbiddenError,
    MailboxSendForbiddenError,
)

_STORE: dict[str, dict[str, Any]] = {}


def reset_fixture_mailbox_store() -> None:
    _STORE.clear()


class FixtureMailboxClient:
    """Idempotent in-memory mailbox drafts for tests and fixture mode."""

    def create_draft(self, request: MailboxDraftRequest) -> MailboxDraftResult:
        if request.client_recipient_email and not request.reviewed:
            raise MailboxClientRecipientForbiddenError()
        existing = _STORE.get(request.idempotency_key)
        if existing is not None:
            return MailboxDraftResult(
                provider_draft_id=str(existing["provider_draft_id"]),
                idempotency_key=request.idempotency_key,
                meeting_owner_email=str(existing["meeting_owner_email"]),
                client_recipient_active=bool(existing.get("client_recipient_active")),
                reused_existing=True,
            )
        provider_draft_id = str(
            uuid5(
                NAMESPACE_URL,
                f"fixture-mailbox:{request.idempotency_key}",
            )
        )
        client_active = bool(request.client_recipient_email and request.reviewed)
        _STORE[request.idempotency_key] = {
            "provider_draft_id": provider_draft_id,
            "meeting_owner_email": request.meeting_owner_email,
            "subject": request.subject,
            "body": request.body,
            "client_recipient_active": client_active,
            "client_recipient_email": request.client_recipient_email if client_active else None,
            "reviewed": request.reviewed,
        }
        return MailboxDraftResult(
            provider_draft_id=provider_draft_id,
            idempotency_key=request.idempotency_key,
            meeting_owner_email=request.meeting_owner_email,
            client_recipient_active=client_active,
            reused_existing=False,
        )

    def send_draft(self, provider_draft_id: str) -> None:
        raise MailboxSendForbiddenError(
            f"Fixture mailbox refuses send for draft {provider_draft_id}."
        )


def mailbox_draft_idempotency_key(*, opportunity_id: str, followup_job_id: str) -> str:
    digest = hashlib.sha256(f"{opportunity_id}:{followup_job_id}".encode("utf-8")).hexdigest()
    return f"followup-mailbox:{digest}"
