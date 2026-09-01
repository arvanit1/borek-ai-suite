"""Framework generation orchestration for Endrit ES-5 / ES-9 / ES-13 (AT-41)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from app.config import settings
from app.services import job_service
from app.services.api_errors import bad_request, not_found
from app.services.data import DataStore
from app.services.deck_assets import deck_assets_root
from app.services.es13_confirm import apply_es13_confirm_gate
from app.services.es32_job_observability import (
    apply_framework_job_observability,
    build_framework_job_observability,
)
from app.services.framework_status import require_reviewable_framework
from app.services.stage_a_orchestration import generate_framework_from_transcripts
from services.framework.rendering.customer_docx import render_customer_docx
from services.framework.rendering.customer_pdf import render_customer_pdf
from services.framework.review_insights import (
    attach_review_insights,
    build_review_payload,
    opportunity_pii_redaction_enabled,
)


def enqueue_framework_generate(store: DataStore, *, opportunity_id: UUID, user_id: UUID):
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    framework_version_id = uuid.uuid4()
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="framework_generation",
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
    return {"id": framework_version_id}, job


def execute_framework_generate(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_version_id: UUID,
):
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    framework_json = generate_framework_from_transcripts(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
    )
    if not framework_json.get("review_summary"):
        framework_json = attach_review_insights(
            framework_json,
            pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
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
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    refreshed = attach_review_insights(
        dict(framework_json),
        pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
    )
    return store.update_latest_framework(
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_json=refreshed,
    )


def get_framework_review(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
) -> dict:
    row = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    framework_json = dict(row["framework_json"])
    if not framework_json.get("review_summary"):
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
) -> dict[str, Any]:
    payload = build_framework_job_observability(
        framework_json=framework_json,
        opportunity_id=str(opportunity_id),
        framework_version_id=str(framework_version_id),
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
