"""BT-33 follow-up job orchestration — extraction → render → mailbox draft."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any
from uuid import UUID

from app.config import settings
from app.schemas.jobs import JobStage, pipeline_stages_for_job_type
from app.services import job_service
from app.services.audit.audit_log import AuditAction, AuditObjectType, record_audit_event
from app.services.data import DataStore
from app.services.followup_egress import (
    enforce_followup_extraction_egress,
    enforce_followup_mailbox_egress,
    extraction_egress_inventory,
    mailbox_egress_inventory,
)
from app.services.followup_rollout import assert_followup_project_allowed
from services.followup.extraction import extract_followup
from services.followup.rendering import render_followup_draft
from services.mailbox import (
    MailboxDraftRequest,
    MailboxSendForbiddenError,
    build_mailbox_provider,
    mailbox_draft_idempotency_key,
)

FOLLOWUP_JOB_TYPE = "followup_generation"


def _stage_should_run(resume_stage: JobStage, target: JobStage, job_type: str) -> bool:
    pipeline = pipeline_stages_for_job_type(job_type)
    if resume_stage not in pipeline or target not in pipeline:
        return True
    return pipeline.index(resume_stage) <= pipeline.index(target)


def _followup_state(job: job_service.Job) -> dict[str, Any]:
    raw = (job.result_json or {}).get("followup")
    return dict(raw) if isinstance(raw, dict) else {}


def _draft_idempotency_key(job_id: UUID) -> str:
    return f"followup-draft:{job_id}"


def enqueue_followup_generate(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    transcript_id: UUID,
    project_key: str,
    project_statics: dict[str, Any],
    meeting_owner_email: str,
    calendar_meeting_date: str | None = None,
    attachment_name: str | None = None,
    client_recipient_email: str | None = None,
) -> tuple[dict[str, Any], job_service.Job, bool]:
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    assert_followup_project_allowed(project_key)
    existing = job_service.reuse_active_generation_job(
        store,
        opportunity_id,
        stage_group="followup",
        job_type=FOLLOWUP_JOB_TYPE,
    )
    if existing is not None:
        draft = store.get_followup_draft(opportunity_id=opportunity_id, user_id=user_id)
        return (
            {"job_id": str(existing.id), "draft_id": str(draft["id"]) if draft else None},
            existing,
            True,
        )

    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type=FOLLOWUP_JOB_TYPE,
        enqueue={
            "user_id": str(user_id),
            "transcript_id": str(transcript_id),
            "project_key": project_key,
            "project_statics": project_statics,
            "meeting_owner_email": meeting_owner_email,
            "calendar_meeting_date": calendar_meeting_date,
            "attachment_name": attachment_name,
            "client_recipient_email": client_recipient_email,
        },
        repository=store,
    )
    from app.worker import run_followup_generation_task

    args = (str(job.id), str(opportunity_id), str(user_id))
    if settings.API_DATA_BACKEND == "memory":
        run_followup_generation_task.run(*args)
    else:
        run_followup_generation_task.delay(*args)
    record_audit_event(
        store,
        actor_id=user_id,
        action=AuditAction.FOLLOWUP_GENERATE,
        object_type=AuditObjectType.OPPORTUNITY,
        object_id=opportunity_id,
    )
    draft = store.get_followup_draft(opportunity_id=opportunity_id, user_id=user_id)
    return (
        {"job_id": str(job.id), "draft_id": str(draft["id"]) if draft else None},
        job,
        False,
    )


def run_followup_extraction_stage(
    store: DataStore,
    *,
    job_id: UUID,
    opportunity_id: UUID,
    user_id: UUID,
    transcript: str,
    calendar_meeting_date: str | None,
    complete: Any | None = None,
) -> dict[str, Any]:
    inventory = extraction_egress_inventory(
        transcript=transcript,
        calendar_meeting_date=calendar_meeting_date,
    )
    enforce_followup_extraction_egress(
        inventory,
        opportunity_id=str(opportunity_id),
        store=store,
        actor_id=user_id,
    )
    return extract_followup(
        transcript,
        calendar_meeting_date=calendar_meeting_date,
        opportunity_id=str(opportunity_id),
        complete=complete,
    )


def run_followup_generation(
    store: DataStore,
    *,
    job_id: UUID,
    opportunity_id: UUID,
    user_id: UUID,
    extraction_complete: Any | None = None,
    force_fail_stage: JobStage | None = None,
) -> job_service.Job:
    job = job_service.get_job(job_id, repository=store)
    if job is None:
        raise job_service.JobNotFoundError(str(job_id))
    enqueue = (job.result_json or {}).get("_enqueue") or {}
    project_key = str(enqueue.get("project_key") or "")
    assert_followup_project_allowed(project_key)

    resume_stage = job.current_stage
    state = _followup_state(job)

    try:
        if _stage_should_run(resume_stage, JobStage.FOLLOWUP_EXTRACTION, job.job_type):
            job = job_service.ensure_stage(
                job_id,
                JobStage.FOLLOWUP_EXTRACTION,
                repository=store,
            )
            if force_fail_stage == JobStage.FOLLOWUP_EXTRACTION:
                raise RuntimeError("forced extraction failure")
            if not state.get("extraction"):
                transcript_id = UUID(str(enqueue["transcript_id"]))
                transcript_row = store.get_transcript(
                    opportunity_id=opportunity_id,
                    transcript_id=transcript_id,
                    user_id=user_id,
                )
                transcript_text = bytes(transcript_row["content"]).decode("utf-8")
                extraction = run_followup_extraction_stage(
                    store,
                    job_id=job_id,
                    opportunity_id=opportunity_id,
                    user_id=user_id,
                    transcript=transcript_text,
                    calendar_meeting_date=enqueue.get("calendar_meeting_date"),
                    complete=extraction_complete,
                )
                state["extraction"] = extraction
                job = job_service.record_result_checkpoint(
                    job_id,
                    {"followup": state},
                    repository=store,
                )

        if _stage_should_run(resume_stage, JobStage.FOLLOWUP_RENDERING, job.job_type):
            job = job_service.ensure_stage(
                job_id,
                JobStage.FOLLOWUP_RENDERING,
                repository=store,
            )
            if force_fail_stage == JobStage.FOLLOWUP_RENDERING:
                raise RuntimeError("forced rendering failure")
            state = _followup_state(job)
            extraction = state.get("extraction")
            if not extraction:
                raise RuntimeError("Missing extraction checkpoint for rendering.")
            if not state.get("rendered"):
                rendered = render_followup_draft(
                    extraction,
                    enqueue["project_statics"],
                    attachment_name=enqueue.get("attachment_name"),
                    reviewed=False,
                )
                state["rendered"] = rendered
                draft_row = store.upsert_followup_draft(
                    idempotency_key=_draft_idempotency_key(job_id),
                    record={
                        "opportunity_id": opportunity_id,
                        "job_id": job_id,
                        "meeting_owner_id": user_id,
                        "meeting_owner_email": str(enqueue["meeting_owner_email"]),
                        "project_key": project_key,
                        "extraction_json": extraction,
                        "subject": rendered["subject"],
                        "body": rendered["body"],
                        "review_flags": rendered.get("review_flags") or [],
                        "attachment_name": rendered.get("attachment_name"),
                        "status": "draft",
                        "provider_draft_id": state.get("provider_draft_id"),
                    },
                )
                state["draft_id"] = str(draft_row["id"])
                job = job_service.record_result_checkpoint(
                    job_id,
                    {"followup": state},
                    repository=store,
                )

        if _stage_should_run(resume_stage, JobStage.FOLLOWUP_DRAFT, job.job_type):
            job = job_service.ensure_stage(job_id, JobStage.FOLLOWUP_DRAFT, repository=store)
            if force_fail_stage == JobStage.FOLLOWUP_DRAFT:
                raise RuntimeError("forced mailbox failure")
            state = _followup_state(job)
            rendered = state.get("rendered")
            if not rendered:
                raise RuntimeError("Missing rendered draft checkpoint.")
            if not state.get("provider_draft_id"):
                mailbox_key = mailbox_draft_idempotency_key(
                    opportunity_id=str(opportunity_id),
                    followup_job_id=str(job_id),
                )
                inventory = mailbox_egress_inventory(
                    subject=str(rendered["subject"]),
                    body=str(rendered["body"]),
                    meeting_owner_email=str(enqueue["meeting_owner_email"]),
                    client_recipient_email=enqueue.get("client_recipient_email"),
                    reviewed=False,
                )
                enforce_followup_mailbox_egress(
                    inventory,
                    opportunity_id=str(opportunity_id),
                    reviewed=False,
                    store=store,
                    actor_id=user_id,
                )
                provider = build_mailbox_provider(settings.MAILBOX_EXECUTION_MODE)
                result = provider.create_draft(
                    MailboxDraftRequest(
                        idempotency_key=mailbox_key,
                        opportunity_id=str(opportunity_id),
                        followup_job_id=str(job_id),
                        meeting_owner_email=str(enqueue["meeting_owner_email"]),
                        subject=str(rendered["subject"]),
                        body=str(rendered["body"]),
                        reviewed=False,
                        attachment_name=rendered.get("attachment_name"),
                    )
                )
                state["provider_draft_id"] = result.provider_draft_id
                state["mailbox_reused"] = result.reused_existing
                draft_id = state.get("draft_id")
                if draft_id:
                    store.update_followup_draft(
                        opportunity_id=opportunity_id,
                        user_id=user_id,
                        draft_id=UUID(str(draft_id)),
                        updates={"provider_draft_id": result.provider_draft_id},
                    )
                job = job_service.record_result_checkpoint(
                    job_id,
                    {"followup": state},
                    repository=store,
                )

        return job_service.complete_job(
            job_id,
            repository=store,
            result_json={
                "followup": {
                    **state,
                    "review_status": "pending",
                }
            },
        )
    except Exception as exc:
        job = job_service.get_job(job_id, repository=store) or job
        active_stage = job.current_stage
        if active_stage in {JobStage.QUEUED, JobStage.COMPLETED, JobStage.FAILED}:
            active_stage = resume_stage
        if active_stage == JobStage.QUEUED:
            active_stage = JobStage.FOLLOWUP_EXTRACTION
        retryable = getattr(exc, "retryable", None)
        if retryable is None:
            from app.services.followup_rollout import FollowupRolloutError

            retryable = not isinstance(
                exc,
                (MailboxSendForbiddenError, FollowupRolloutError),
            )
        code = getattr(exc, "code", None) or "FOLLOWUP_PIPELINE_FAILED"
        return job_service.fail_job(
            job_id,
            str(code),
            str(exc),
            active_stage,
            bool(retryable),
            repository=store,
        )


def refuse_followup_send() -> None:
    raise MailboxSendForbiddenError()
