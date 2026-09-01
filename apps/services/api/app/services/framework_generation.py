"""Framework generation orchestration for Endrit ES-5 / ES-9 / ES-13 (AT-41)."""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException

from app.config import settings
from app.services import job_service
from app.services.api_errors import bad_request, not_found
from app.services.data import DataStore
from app.services.es13_confirm import apply_es13_confirm_gate
from app.services.framework_status import require_reviewable_framework
from app.services.stage_a_orchestration import generate_framework_from_transcripts
from app.services.deck_assets import deck_assets_root
from services.framework.rendering.customer_pdf import render_customer_pdf


def enqueue_framework_generate(store: DataStore, *, opportunity_id: UUID, user_id: UUID):
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
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
):
    framework_json = generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
    )
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
    framework_version = store.regenerate_chapter(
        opportunity_id=opportunity_id,
        user_id=user_id,
        chapter_id=chapter_id,
    )
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="framework_regenerate_chapter",
        enqueue={
            "framework_version_id": str(framework_version["id"]),
            "chapter_id": chapter_id,
        },
        repository=store,
    )
    from app.worker import run_framework_regenerate_chapter_task

    args = (str(job.id), str(framework_version["id"]), chapter_id)
    if settings.API_DATA_BACKEND == "memory":
        run_framework_regenerate_chapter_task.run(*args)
    else:
        run_framework_regenerate_chapter_task.delay(*args)
    return framework_version, job


def execute_framework_render(
    store: DataStore,
    *,
    framework_version_id: UUID,
    user_id: UUID,
) -> Path:
    framework = store.get_framework_version(
        framework_version_id=framework_version_id,
        user_id=user_id,
    )
    output_dir = deck_assets_root() / "frameworks" / str(framework_version_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "report.pdf"
    output_path.write_bytes(
        render_customer_pdf(
            framework["framework_json"],
            lang=str(framework["framework_json"].get("language") or "en"),
        )
    )
    return output_path


def resolve_framework_render_path(framework_version_id: UUID) -> Path:
    return deck_assets_root() / "frameworks" / str(framework_version_id) / "report.pdf"


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
    confirmed_json = apply_es13_confirm_gate(row["framework_json"])
    return store.confirm_framework(
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_version_id=framework_version_id,
        confirmed_framework_json=confirmed_json,
    )


def update_framework(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_json: dict,
):
    return store.update_latest_framework(
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_json=framework_json,
    )


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
