"""BT-25 durable continuation between existing Stage B jobs."""

from __future__ import annotations

import logging
from uuid import UUID

from app.schemas.jobs import JobStage, JobStatus
from app.services import job_service, presentation_generation
from app.services.api_errors import error_fields_from_exception
from app.services.audit import AuditAction, AuditObjectType, record_audit_event
from app.services.data import DataStore

logger = logging.getLogger(__name__)


def _enqueue_context(job: job_service.Job) -> dict:
    raw = (job.result_json or {}).get("_enqueue")
    return dict(raw) if isinstance(raw, dict) else {}


def _record_failed_generation_job(
    store: DataStore,
    planning_job: job_service.Job,
    context: dict,
    exc: BaseException,
) -> None:
    """Make a continuation failure visible as a presentation_generation job.

    Planning is already COMPLETED, so the client can only observe generation.
    Without this row the UI times out as PRESENTATION_PIPELINE_HANDOFF_MISSING.
    """
    code, message, retryable = error_fields_from_exception(exc)
    existing = job_service.reuse_active_generation_job(
        store,
        planning_job.opportunity_id,
        stage_group="presentation",
        job_type="presentation_generation",
    )
    job = existing or job_service.create_job(
        opportunity_id=planning_job.opportunity_id,
        job_type="presentation_generation",
        enqueue={
            "user_id": context.get("user_id"),
            "planning_job_id": str(planning_job.id),
            "continuation_failed": True,
        },
        repository=store,
    )
    if not job_service.is_non_terminal_job(job):
        return
    if code == "JOB_FAILED":
        code = "PRESENTATION_CONTINUATION_FAILED"
    job_service.fail_job(
        job.id,
        code,
        message,
        JobStage.SLIDE_GENERATING,
        retryable,
        repository=store,
    )


def continue_after_planning(
    store: DataStore,
    *,
    planning_job_id: UUID,
):
    """Start/reuse presentation generation only for an opted-in completed plan."""
    planning_job = job_service.get_job(planning_job_id, repository=store)
    if planning_job is None:
        raise job_service.JobNotFoundError(str(planning_job_id))
    if planning_job.job_type != "presentation_planning":
        raise RuntimeError("BT-25 continuation requires a presentation_planning job")

    context = _enqueue_context(planning_job)
    if not planning_job.auto_continue:
        return None
    if planning_job.status != JobStatus.COMPLETED:
        raise RuntimeError("BT-25 continuation requires planning status COMPLETED")

    try:
        user_id = UUID(str(context["user_id"]))
        framework_version_id = UUID(str(context["framework_version_id"]))
        result_plan_id = (planning_job.result_json or {}).get("presentation_plan_id")
        if not result_plan_id:
            raise RuntimeError("Completed planning job is missing presentation_plan_id")
        presentation_plan_id = UUID(str(result_plan_id))
        if str(context.get("presentation_plan_id")) != str(presentation_plan_id):
            raise RuntimeError("Completed planning result does not match its requested plan ID")

        plan = store.get_presentation_plan(
            presentation_plan_id=presentation_plan_id,
            user_id=user_id,
        )
        if plan["framework_version_id"] != framework_version_id:
            raise RuntimeError("Persisted PresentationPlan belongs to a different Framework version")

        presentation, resolved_plan, generation_job, is_existing = (
            presentation_generation.enqueue_presentation_generate(
                store,
                opportunity_id=planning_job.opportunity_id,
                user_id=user_id,
                framework_version_id=framework_version_id,
                presentation_plan_id=presentation_plan_id,
                name=None,
                journey_stage=context.get("journey_stage"),
            )
        )
        record_audit_event(
            store,
            actor_id=user_id,
            action=AuditAction.PRESENTATION_GENERATE,
            object_type=AuditObjectType.PRESENTATION,
            object_id=presentation.get("id") or planning_job.opportunity_id,
        )
        return presentation, resolved_plan, generation_job, is_existing
    except Exception as exc:
        try:
            _record_failed_generation_job(store, planning_job, context, exc)
        except Exception:
            logger.exception(
                "Failed to persist a generation job after planning %s completed",
                planning_job_id,
            )
        raise
