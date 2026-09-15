"""BT-33 review handoff — backend contract for MS-32 without UI."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.schemas.followups import FollowupDraftResponse
from app.services.data import DataStore
from app.services.followup_egress import (
    enforce_followup_mailbox_egress,
    mailbox_egress_inventory,
)
from app.services.followup_pipeline import refuse_followup_send
from services.followup.errors import FollowupRenderError
from services.mailbox import MailboxDraftRequest, build_mailbox_provider
from app.config import settings


def _to_response(row: dict) -> FollowupDraftResponse:
    return FollowupDraftResponse(
        id=str(row["id"]),
        opportunity_id=str(row["opportunity_id"]),
        job_id=str(row["job_id"]),
        subject=str(row["subject"]),
        body=str(row["body"]),
        review_flags=list(row.get("review_flags") or []),
        attachment_name=row.get("attachment_name"),
        status=row["status"],
        provider_draft_id=row.get("provider_draft_id"),
        reviewed_at=row.get("reviewed_at"),
        sent_at=row.get("sent_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_followup_draft(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
) -> FollowupDraftResponse | None:
    row = store.get_followup_draft(opportunity_id=opportunity_id, user_id=user_id)
    if row is None:
        return None
    return _to_response(row)


def update_followup_draft(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    subject: str,
    body: str,
) -> FollowupDraftResponse:
    row = store.get_followup_draft(opportunity_id=opportunity_id, user_id=user_id)
    if row is None:
        raise FollowupRenderError("Follow-up draft not found.", code="FOLLOWUP_DRAFT_NOT_FOUND")
    if row["status"] != "draft":
        raise FollowupRenderError(
            "Only draft-status follow-ups can be edited.",
            code="FOLLOWUP_DRAFT_NOT_EDITABLE",
        )
    updated = store.update_followup_draft(
        opportunity_id=opportunity_id,
        user_id=user_id,
        draft_id=row["id"],
        updates={"subject": subject, "body": body},
    )
    return _to_response(updated)


def confirm_followup_review(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    client_recipient_email: str | None = None,
) -> FollowupDraftResponse:
    row = store.get_followup_draft(opportunity_id=opportunity_id, user_id=user_id)
    if row is None:
        raise FollowupRenderError("Follow-up draft not found.", code="FOLLOWUP_DRAFT_NOT_FOUND")
    if row["status"] != "draft":
        raise FollowupRenderError(
            "Review can only be confirmed from draft status.",
            code="FOLLOWUP_REVIEW_INVALID",
        )
    reviewed_at = datetime.now(UTC)
    owner_email = str(row.get("meeting_owner_email") or "owner@example.com")
    inventory = mailbox_egress_inventory(
        subject=str(row["subject"]),
        body=str(row["body"]),
        meeting_owner_email=owner_email,
        client_recipient_email=client_recipient_email,
        reviewed=True,
    )
    enforce_followup_mailbox_egress(
        inventory,
        opportunity_id=str(opportunity_id),
        reviewed=True,
        store=store,
        actor_id=user_id,
    )
    provider = build_mailbox_provider(settings.MAILBOX_EXECUTION_MODE)
    if row.get("provider_draft_id"):
        provider.create_draft(
            MailboxDraftRequest(
                idempotency_key=f"followup-reviewed:{row['id']}",
                opportunity_id=str(opportunity_id),
                followup_job_id=str(row["job_id"]),
                meeting_owner_email=owner_email,
                subject=str(row["subject"]),
                body=str(row["body"]),
                reviewed=True,
                client_recipient_email=client_recipient_email,
                attachment_name=row.get("attachment_name"),
            )
        )
    updated = store.update_followup_draft(
        opportunity_id=opportunity_id,
        user_id=user_id,
        draft_id=row["id"],
        updates={"status": "reviewed", "reviewed_at": reviewed_at},
    )
    return _to_response(updated)


def record_followup_delivery(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    delivery_status: str,
    final_subject: str | None = None,
    final_body: str | None = None,
) -> dict:
    row = store.get_followup_draft(opportunity_id=opportunity_id, user_id=user_id)
    if row is None:
        raise FollowupRenderError("Follow-up draft not found.", code="FOLLOWUP_DRAFT_NOT_FOUND")
    if row["status"] != "reviewed":
        raise FollowupRenderError(
            "Delivery can only be recorded after review.",
            code="FOLLOWUP_DELIVERY_FORBIDDEN",
        )
    if delivery_status not in {"sent", "sent_unknown"}:
        raise FollowupRenderError("Invalid delivery status.", code="FOLLOWUP_DELIVERY_INVALID")
    sent_at = datetime.now(UTC)
    draft_status = delivery_status
    store.update_followup_draft(
        opportunity_id=opportunity_id,
        user_id=user_id,
        draft_id=row["id"],
        updates={"status": draft_status, "sent_at": sent_at},
    )
    log = store.create_followup_sent_log(
        {
            "opportunity_id": opportunity_id,
            "followup_draft_id": row["id"],
            "meeting_owner_id": user_id,
            "generated_subject": row["subject"],
            "generated_body": row["body"],
            "final_subject": final_subject,
            "final_body": final_body,
            "delivery_status": delivery_status,
        }
    )
    return log


def attempt_followup_send() -> None:
    refuse_followup_send()
