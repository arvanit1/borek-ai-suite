"""MS-24: one round-trip summary for the recent-work home list."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.services.job_service import select_reconnect_job

_ACTIVE_JOB_STATUSES = {"QUEUED", "RUNNING"}


def list_recent_work_snapshots(store: Any, *, user_id: UUID) -> list[dict[str, Any]]:
    opportunities = store.list_opportunities(user_id=user_id)
    if not opportunities:
        return []
    index = store.load_recent_work_index(
        user_id=user_id,
        opportunity_ids=[row["id"] for row in opportunities],
    )
    return [_snapshot_for(row, index) for row in opportunities]


def _snapshot_for(opportunity: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    opp_id = str(opportunity["id"])
    transcripts = index.get("transcripts", {}).get(opp_id) or []
    framework = index.get("frameworks", {}).get(opp_id)
    plan = index.get("plans", {}).get(opp_id)
    presentation = index.get("presentations", {}).get(opp_id)
    jobs = index.get("jobs", {}).get(opp_id) or []
    workflow = _select_workflow_job(jobs)
    version_status = str((presentation or {}).get("version_status") or "")
    presentation_id = (presentation or {}).get("id")
    return {
        "opportunity": {
            "id": opportunity["id"],
            "client_name": opportunity["client_name"],
            "opportunity_name": opportunity["opportunity_name"],
            "created_by": opportunity["created_by"],
            "created_at": opportunity["created_at"],
            "updated_at": opportunity["updated_at"],
        },
        "transcript_count": len(transcripts),
        "framework_status": None if framework is None else framework.get("status"),
        "has_plan": plan is not None,
        "presentation_id": presentation_id,
        "presentation_name": None if presentation is None else presentation.get("name"),
        "deck": (
            {"pptx_download_url": f"/presentations/{presentation_id}/download/pptx"}
            if presentation_id and version_status == "ready"
            else None
        ),
        "resource_load_failed": False,
        "activity_at": _latest_activity(
            opportunity.get("updated_at"),
            opportunity.get("created_at"),
            *[row.get("created_at") for row in transcripts],
            None if framework is None else framework.get("created_at"),
            None if plan is None else plan.get("created_at"),
            None if presentation is None else presentation.get("created_at"),
            None if workflow is None else workflow.get("completed_at"),
            None if workflow is None else workflow.get("started_at"),
        ),
        "job": None
        if workflow is None
        else {
            "job_type": workflow.get("job_type"),
            "status": _status_value(workflow.get("status")),
            "current_stage": workflow.get("current_stage"),
            "auto_continue": bool(workflow.get("auto_continue")),
        },
    }


def _select_workflow_job(jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not jobs:
        return None
    latest = max(jobs, key=lambda row: (_as_datetime(row.get("created_at")), str(row.get("id") or "")))
    candidates = [
        select_reconnect_job(jobs, stage_group="framework"),
        select_reconnect_job(jobs, stage_group="presentation"),
        latest,
    ]
    relevant = [
        row
        for row in candidates
        if row is not None and "framework_render" not in str(row.get("job_type") or "").lower()
    ]
    active = [row for row in relevant if _status_value(row.get("status")) in _ACTIVE_JOB_STATUSES]
    pool = active or relevant
    if not pool:
        return None
    return max(
        pool,
        key=lambda row: (
            _as_datetime(row.get("completed_at") or row.get("started_at") or row.get("created_at")),
            str(row.get("id") or ""),
        ),
    )


def _latest_activity(*values: Any) -> str | None:
    parsed = [_as_datetime(value) for value in values if value is not None and value != ""]
    valid = [item for item in parsed if item != datetime.min.replace(tzinfo=UTC)]
    if not valid:
        return None
    latest = max(valid)
    return latest.isoformat().replace("+00:00", "Z")


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str) and value:
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.min.replace(tzinfo=UTC)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    return datetime.min.replace(tzinfo=UTC)


def _status_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value or "")
