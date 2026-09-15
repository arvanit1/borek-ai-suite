"""BT-33 follow-up pipeline and MS-32 review handoff routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.followups import (
    FollowupDeliveryRecordRequest,
    FollowupDraftResponse,
    FollowupDraftUpdateRequest,
    FollowupGenerateRequest,
    FollowupReviewConfirmResponse,
)
from app.schemas.jobs import JobEnqueueResponse
from app.services.audit.audit_log import AuditAction, AuditObjectType, record_audit_event
from app.auth import get_current_user
from app.services import job_service
from app.services.followup_pipeline import enqueue_followup_generate
from app.services.followup_review import (
    attempt_followup_send,
    confirm_followup_review,
    get_followup_draft,
    record_followup_delivery,
    update_followup_draft,
)
from app.services.followup_rollout import FollowupRolloutError
from services.followup.errors import FollowupRenderError
from services.mailbox.errors import MailboxSendForbiddenError

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post(
    "/{opportunity_id}/followup/generate",
    response_model=JobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_followup(
    opportunity_id: UUID,
    payload: FollowupGenerateRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> JobEnqueueResponse:
    try:
        _result, job, existing = enqueue_followup_generate(
            store,
            opportunity_id=opportunity_id,
            user_id=user.id,
            transcript_id=UUID(payload.transcript_id),
            project_key=payload.project_key,
            project_statics=payload.project_statics,
            meeting_owner_email=payload.meeting_owner_email,
            calendar_meeting_date=payload.calendar_meeting_date,
            attachment_name=payload.attachment_name,
            client_recipient_email=payload.client_recipient_email,
        )
    except FollowupRolloutError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return JobEnqueueResponse(
        job_id=str(job.id),
        status=job_service.enqueue_status_for_job(job, existing=existing),
        is_existing_job=existing,
    )


@router.get(
    "/{opportunity_id}/followup/draft",
    response_model=FollowupDraftResponse | None,
)
def fetch_followup_draft(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FollowupDraftResponse | None:
    return get_followup_draft(store, opportunity_id=opportunity_id, user_id=user.id)


@router.patch(
    "/{opportunity_id}/followup/draft",
    response_model=FollowupDraftResponse,
)
def save_followup_draft(
    opportunity_id: UUID,
    payload: FollowupDraftUpdateRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FollowupDraftResponse:
    try:
        return update_followup_draft(
            store,
            opportunity_id=opportunity_id,
            user_id=user.id,
            subject=payload.subject,
            body=payload.body,
        )
    except FollowupRenderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post(
    "/{opportunity_id}/followup/review/confirm",
    response_model=FollowupReviewConfirmResponse,
)
def confirm_review(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
    client_recipient_email: str | None = None,
) -> FollowupReviewConfirmResponse:
    try:
        draft = confirm_followup_review(
            store,
            opportunity_id=opportunity_id,
            user_id=user.id,
            client_recipient_email=client_recipient_email,
        )
    except FollowupRenderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FOLLOWUP_REVIEW,
        object_type=AuditObjectType.OPPORTUNITY,
        object_id=opportunity_id,
    )
    return FollowupReviewConfirmResponse(
        draft=draft,
        provider_draft_id=draft.provider_draft_id,
    )


@router.post("/{opportunity_id}/followup/send", status_code=status.HTTP_403_FORBIDDEN)
def send_followup_forbidden(opportunity_id: UUID) -> None:
    try:
        attempt_followup_send()
    except MailboxSendForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post("/{opportunity_id}/followup/delivery/record")
def record_delivery(
    opportunity_id: UUID,
    payload: FollowupDeliveryRecordRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> dict:
    try:
        log = record_followup_delivery(
            store,
            opportunity_id=opportunity_id,
            user_id=user.id,
            delivery_status=payload.delivery_status,
            final_subject=payload.final_subject,
            final_body=payload.final_body,
        )
    except FollowupRenderError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FOLLOWUP_DELIVERY_RECORD,
        object_type=AuditObjectType.OPPORTUNITY,
        object_id=opportunity_id,
    )
    return log
