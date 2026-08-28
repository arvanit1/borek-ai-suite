"""Framework generation stub wired for Endrit ES-9 / ES-12 (AT-41)."""

from __future__ import annotations

from uuid import UUID

from app.services import job_service
from app.services.api_errors import bad_request, conflict, not_found
from app.services.data import DataStore
from app.services.es13_confirm import apply_es13_confirm_gate


def enqueue_framework_generate(store: DataStore, *, opportunity_id: UUID, user_id: UUID):
    framework_version = store.generate_framework_stub(
        opportunity_id=opportunity_id,
        user_id=user_id,
    )
    job = job_service.create_job(opportunity_id=opportunity_id, job_type="framework_generation")
    return framework_version, job


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
    )
    return framework_version, job


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

    if row["status"] == "confirmed":
        raise conflict("FRAMEWORK_ALREADY_CONFIRMED", "Framework version is already confirmed")
    if row["status"] != "draft":
        raise bad_request(
            "FRAMEWORK_NOT_CONFIRMABLE",
            f"Framework version status {row['status']} cannot be confirmed",
        )
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
    job = job_service.create_job(opportunity_id=opportunity_id, job_type="framework_render")
    return framework_version, job
