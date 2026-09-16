"""Framework generation orchestration for Endrit ES-5 / ES-9 / ES-13 (AT-41)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.config import settings
from app.services import job_service
from app.services.api_errors import bad_request, conflict, not_found, unprocessable
from app.services.data import DataStore
from app.services.deck_assets import deck_assets_root
from app.services.es13_confirm import apply_es13_confirm_gate
from app.services.es32_job_observability import (
    apply_framework_job_observability,
    build_framework_job_observability,
)
from app.services.framework_status import require_confirmed_framework, require_reviewable_framework
from app.services.framework_versioning import (
    build_framework_successor,
    framework_source_revision,
    framework_transition_id,
)
from app.services.stage_a_orchestration import generate_framework_from_transcripts
from app.services.stage_a_orchestration import regenerate_framework_chapter_from_transcripts
from services.framework.regenerate_chapter import build_regenerated_framework
from services.framework.rendering.customer_docx import render_customer_docx
from services.framework.rendering.customer_pdf import render_customer_pdf
from services.framework.review_insights import (
    attach_review_insights,
    build_review_payload,
    opportunity_pii_redaction_enabled,
)
from packages.contracts.schema_consumer import (
    FrameworkObjectValidationError,
    validate_framework_object,
)


def enqueue_framework_generate(store: DataStore, *, opportunity_id: UUID, user_id: UUID):
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    transcript_ids = [
        str(source["id"])
        for source in store.list_transcript_sources(
            opportunity_id=opportunity_id,
            user_id=user_id,
        )
    ]
    existing = job_service.reuse_active_generation_job(
        store,
        opportunity_id,
        stage_group="framework",
    )
    if existing is not None:
        framework_version_id = None
        try:
            latest = store.get_latest_framework(
                opportunity_id=opportunity_id,
                user_id=user_id,
            )
            framework_version_id = latest["id"]
        except HTTPException:
            framework_version_id = None
        return {"id": framework_version_id, "existing": True}, existing

    framework_version_id = uuid.uuid4()
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="framework_generation",
        enqueue={
            "user_id": str(user_id),
            "framework_version_id": str(framework_version_id),
            "transcript_ids": transcript_ids,
        },
        repository=store,
    )
    from app.worker import run_framework_generation_task

    args = (
        str(job.id),
        str(opportunity_id),
        str(user_id),
        str(framework_version_id),
    )
    if settings.API_DATA_BACKEND == "memory":
        run_framework_generation_task.run(*args)
    else:
        run_framework_generation_task.delay(*args)
    return {"id": framework_version_id, "existing": False}, job


def execute_framework_generate(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_version_id: UUID,
    job_id: UUID | None = None,
    transcript_ids: list[str] | None = None,
    stage_callback: Any | None = None,
):
    try:
        existing = store.get_framework_version(
            framework_version_id=framework_version_id,
            user_id=user_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    else:
        if existing["opportunity_id"] != opportunity_id:
            raise conflict("FRAMEWORK_VERSION_CONFLICT", "The reserved Framework version already exists")
        return existing

    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    framework_json = generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
        job_id=job_id,
        transcript_ids=transcript_ids,
        stage_callback=stage_callback,
    )
    if not framework_json.get("review_summary"):
        framework_json = attach_review_insights(
            framework_json,
            pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
        )
    if stage_callback is not None:
        stage_callback("validation")
    _validate_framework_for_persistence(framework_json)
    framework_version = store.create_framework_version(
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_json=framework_json,
        status="draft",
        framework_version_id=framework_version_id,
    )
    return framework_version


def enqueue_regenerate_chapter(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    chapter_id: str,
):
    framework_version = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
    require_reviewable_framework(framework_version["status"], action="regenerate")
    if not any(
        str(chapter.get("chapter_id")) == chapter_id
        for chapter in framework_version["framework_json"].get("chapters") or []
    ):
        raise bad_request("INVALID_CHAPTER_ID", f"Chapter {chapter_id} was not found")
    destination_id = uuid.uuid4()
    source_revision = framework_source_revision(framework_version)
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="framework_regenerate_chapter",
        enqueue={
            "user_id": str(user_id),
            "source_framework_version_id": str(framework_version["id"]),
            "source_revision": source_revision,
            "framework_version_id": str(destination_id),
            "chapter_id": chapter_id,
        },
        repository=store,
    )
    from app.worker import run_framework_regenerate_chapter_task

    args = (
        str(job.id),
        str(destination_id),
        chapter_id,
        str(opportunity_id),
        str(user_id),
        str(framework_version["id"]),
        source_revision,
    )
    if settings.API_DATA_BACKEND == "memory":
        run_framework_regenerate_chapter_task.run(*args)
    else:
        run_framework_regenerate_chapter_task.delay(*args)
    return {"id": destination_id}, job


def execute_framework_regenerate_chapter(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    source_framework_version_id: UUID,
    framework_version_id: UUID,
    chapter_id: str,
    source_revision: str,
    stage_callback: Any | None = None,
) -> dict[str, Any]:
    try:
        existing = store.get_framework_version(
            framework_version_id=framework_version_id,
            user_id=user_id,
        )
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    else:
        previous_id = str(existing["framework_json"].get("previous_version_id") or "")
        if existing["opportunity_id"] != opportunity_id or previous_id != str(source_framework_version_id):
            raise conflict("FRAMEWORK_VERSION_CONFLICT", "The reserved Framework version already exists")
        return existing

    source = store.get_framework_version(
        framework_version_id=source_framework_version_id,
        user_id=user_id,
    )
    if source["opportunity_id"] != opportunity_id:
        raise not_found("FRAMEWORK_NOT_FOUND", f"Framework version {source_framework_version_id} was not found")
    require_reviewable_framework(source["status"], action="regenerate")
    if framework_source_revision(source) != source_revision:
        raise conflict("FRAMEWORK_VERSION_CONFLICT", "The source Framework changed before regeneration started")
    replacement = regenerate_framework_chapter_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework=source["framework_json"],
        chapter_id=chapter_id,
        stage_callback=stage_callback,
    )
    if stage_callback is not None:
        stage_callback("validation")
    framework_json = build_regenerated_framework(
        source["framework_json"],
        chapter_id,
        replacement,
        source_framework_version_id=str(source_framework_version_id),
        new_version=int(source["version_number"]) + 1,
    )
    current_source = store.get_framework_version(
        framework_version_id=source_framework_version_id,
        user_id=user_id,
    )
    if framework_source_revision(current_source) != source_revision:
        raise conflict("FRAMEWORK_VERSION_CONFLICT", "The source Framework changed during regeneration")
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    framework_json = attach_review_insights(
        framework_json,
        pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
    )
    _validate_framework_for_persistence(framework_json)
    return store.append_framework_version_transition(
        opportunity_id=opportunity_id,
        user_id=user_id,
        source_framework_version_id=source_framework_version_id,
        framework_version_id=framework_version_id,
        framework_json=framework_json,
        status=source["status"],
        source_revision=source_revision,
        transition="regenerate",
    )


def execute_framework_render(
    store: DataStore,
    *,
    framework_version_id: UUID,
    user_id: UUID,
    output_format: str = "pdf",
) -> Path:
    framework = store.get_framework_version(
        framework_version_id=framework_version_id,
        user_id=user_id,
    )
    output_dir = deck_assets_root() / "frameworks" / str(framework_version_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    lang = str(framework["framework_json"].get("language") or "en")
    if output_format == "docx":
        output_path = output_dir / "report.docx"
        output_path.write_bytes(render_customer_docx(framework["framework_json"], lang=lang))
        return output_path
    output_path = output_dir / "report.pdf"
    output_path.write_bytes(render_customer_pdf(framework["framework_json"], lang=lang))
    return output_path


def resolve_framework_render_path(framework_version_id: UUID, *, output_format: str = "pdf") -> Path:
    suffix = "docx" if output_format == "docx" else "pdf"
    return deck_assets_root() / "frameworks" / str(framework_version_id) / f"report.{suffix}"


def _resolve_draft_framework_row(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_version_id: UUID | None,
) -> dict:
    if framework_version_id is not None:
        row = store.get_framework_version(
            framework_version_id=framework_version_id,
            user_id=user_id,
        )
        if row["opportunity_id"] != opportunity_id:
            raise not_found(
                "FRAMEWORK_NOT_FOUND",
                f"Framework version {framework_version_id} was not found",
            )
    else:
        row = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)

    require_reviewable_framework(row["status"], action="confirm")
    return row


def confirm_framework(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_version_id: UUID | None,
):
    row = _resolve_draft_framework_row(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_version_id=framework_version_id,
    )
    _validate_framework_for_persistence(row["framework_json"])
    gated_json = apply_es13_confirm_gate(row["framework_json"])
    confirmed_json = build_framework_successor(
        row,
        status="confirmed",
        change="Customer report confirmed",
        framework_json=gated_json,
        confirmed_by=user_id,
        rebuild_customer_view=False,
    )
    _validate_framework_for_persistence(confirmed_json)
    return store.append_framework_version_transition(
        opportunity_id=opportunity_id,
        user_id=user_id,
        source_framework_version_id=row["id"],
        framework_version_id=framework_transition_id(row["id"], "confirm"),
        framework_json=confirmed_json,
        status="confirmed",
        source_revision=framework_source_revision(row),
        transition="confirm",
    )


def reopen_framework_for_correction(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
):
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    row = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
    require_confirmed_framework(row["status"])
    framework_json = build_framework_successor(
        row,
        status="in_review",
        change="Reopened for a small correction after presentation generation",
        rebuild_customer_view=False,
    )
    _validate_framework_for_persistence(framework_json)
    return store.append_framework_version_transition(
        opportunity_id=opportunity_id,
        user_id=user_id,
        source_framework_version_id=row["id"],
        framework_version_id=framework_transition_id(row["id"], "reopen"),
        framework_json=framework_json,
        status="in_review",
        source_revision=framework_source_revision(row),
        transition="reopen",
    )


def update_framework(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_json: dict,
):
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    source = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
    require_reviewable_framework(source["status"], action="edit")
    for field in ("opportunity_id", "version", "previous_version_id", "status", "created_at"):
        if framework_json.get(field) != source["framework_json"].get(field):
            raise conflict("FRAMEWORK_VERSION_CONFLICT", f"Framework field {field} changed since this draft was loaded")
    refreshed = attach_review_insights(
        dict(framework_json),
        pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
    )
    successor = build_framework_successor(
        source,
        status=source["status"],
        change="Manual edit via framework review UI",
        framework_json=refreshed,
    )
    _validate_framework_for_persistence(successor)
    return store.append_framework_version_transition(
        opportunity_id=opportunity_id,
        user_id=user_id,
        source_framework_version_id=source["id"],
        framework_version_id=framework_transition_id(source["id"], "edit"),
        framework_json=successor,
        status=source["status"],
        source_revision=framework_source_revision(source),
        transition="edit",
    )


def _validate_framework_for_persistence(framework_json: dict[str, Any]) -> None:
    try:
        validate_framework_object(framework_json)
    except FrameworkObjectValidationError as exc:
        raise unprocessable(
            exc.code,
            str(exc),
            detail={"errors": exc.errors},
        ) from exc


def get_framework_review(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
) -> dict:
    row = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    framework_json = dict(row["framework_json"])
    framework_json = attach_review_insights(
        framework_json,
        pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
    )
    return build_review_payload(framework_json)


def persist_framework_generation_observability(
    job: Any,
    *,
    framework_json: dict,
    opportunity_id: UUID,
    framework_version_id: UUID,
    repository: Any | None = None,
) -> dict[str, Any]:
    payload = build_framework_job_observability(
        framework_json=framework_json,
        opportunity_id=str(opportunity_id),
        framework_version_id=str(framework_version_id),
        job_id=str(getattr(job, "id", "") or ""),
        store=repository,
    )
    apply_framework_job_observability(job, payload)
    return payload


def enqueue_framework_render(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
):
    framework_version = store.get_latest_framework(
        opportunity_id=opportunity_id,
        user_id=user_id,
    )
    if framework_version["status"] != "confirmed":
        from app.services.api_errors import bad_request

        raise bad_request(
            "FRAMEWORK_NOT_CONFIRMED",
            "Framework must be confirmed before render",
        )
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="framework_render",
        enqueue={
            "framework_version_id": str(framework_version["id"]),
            "user_id": str(user_id),
        },
        repository=store,
    )
    from app.worker import run_framework_render_task

    args = (
        str(job.id),
        str(framework_version["id"]),
        str(user_id),
    )
    if settings.API_DATA_BACKEND == "memory":
        run_framework_render_task.run(*args)
    else:
        run_framework_render_task.delay(*args)
    return framework_version, job
