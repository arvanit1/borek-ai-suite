"""Mailbox draft contract — BT-33 provider boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class MailboxDraftRequest:
    idempotency_key: str
    opportunity_id: str
    followup_job_id: str
    meeting_owner_email: str
    subject: str
    body: str
    reviewed: bool = False
    client_recipient_email: str | None = None
    attachment_name: str | None = None


@dataclass(frozen=True)
class MailboxDraftResult:
    provider_draft_id: str
    idempotency_key: str
    meeting_owner_email: str
    client_recipient_active: bool = False
    reused_existing: bool = False


class MailboxProvider(Protocol):
    def create_draft(self, request: MailboxDraftRequest) -> MailboxDraftResult:
        """Create or reuse a mailbox draft. Must never send."""

    def send_draft(self, provider_draft_id: str) -> None:
        """Explicit send — forbidden from BT-33 orchestration."""
