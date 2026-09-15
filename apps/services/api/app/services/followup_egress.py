"""BT-33 O4 egress boundaries for follow-up extraction and mailbox drafts."""

from __future__ import annotations

from typing import Any

from services.security.egress_policy import EgressBlockedError, enforce_external_egress


def enforce_followup_extraction_egress(
    payload: dict[str, Any],
    *,
    opportunity_id: str,
    store: Any | None = None,
    actor_id: Any | None = None,
) -> dict[str, Any]:
    return enforce_external_egress(
        payload,
        provider="anthropic",
        stage="followup_extraction",
        opportunity_id=opportunity_id,
        store=store,
        actor_id=actor_id,
    )


def enforce_followup_mailbox_egress(
    payload: dict[str, Any],
    *,
    opportunity_id: str,
    reviewed: bool,
    store: Any | None = None,
    actor_id: Any | None = None,
) -> dict[str, Any]:
    outbound = dict(payload)
    if not reviewed:
        outbound.pop("client_recipient_email", None)
    return enforce_external_egress(
        outbound,
        provider="outlook",
        stage="followup_draft",
        opportunity_id=opportunity_id,
        store=store,
        actor_id=actor_id,
    )


def extraction_egress_inventory(
    *,
    transcript: str,
    calendar_meeting_date: str | None,
) -> dict[str, Any]:
    return {
        "transcript": transcript,
        "calendar_meeting_date": calendar_meeting_date or "",
    }


def mailbox_egress_inventory(
    *,
    subject: str,
    body: str,
    meeting_owner_email: str,
    client_recipient_email: str | None,
    reviewed: bool,
) -> dict[str, Any]:
    payload = {
        "subject": subject,
        "body": body,
        "meeting_owner_email": meeting_owner_email,
    }
    if reviewed and client_recipient_email:
        payload["client_recipient_email"] = client_recipient_email
    return payload


__all__ = [
    "EgressBlockedError",
    "enforce_followup_extraction_egress",
    "enforce_followup_mailbox_egress",
    "extraction_egress_inventory",
    "mailbox_egress_inventory",
]
