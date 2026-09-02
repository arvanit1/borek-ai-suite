"""BT-25 durable continuation between existing Stage B jobs."""

from __future__ import annotations

from uuid import UUID

from app.schemas.jobs import JobStatus
from app.services import job_service, presentation_generation
from app.services.audit import AuditAction, AuditObjectType, record_audit_event
from app.services.data import DataStore


def _enqueue_context(job: job_service.Job) -> dict:
    raw = (job.result_json or {}).get("_enqueue")
    return dict(raw) if isinstance(raw, dict) else {}


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
