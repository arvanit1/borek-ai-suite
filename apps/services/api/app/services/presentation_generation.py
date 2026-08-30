"""Presentation planning/generation orchestration (AT-42 / AT-43).

BT-1 `plan_presentation` and Group A generators (BT-9..13) are invoked from the
data stores. Group B/C layouts stay metadata stubs until JJ/MS wire their
generators. Deck files remain stub artifacts until the renderer is called.
"""

from __future__ import annotations

from uuid import UUID

from app.schemas.presentations import VALID_LAYOUT_IDS
from app.services import job_service
from app.services.api_errors import bad_request, not_found
from app.services.data import DataStore


def _require_confirmed_framework(
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

    if row["status"] != "confirmed":
        raise bad_request(
            "FRAMEWORK_NOT_CONFIRMED",
            "Framework must be confirmed before presentation planning or generation",
        )
    return row


def _resolve_presentation_plan(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_version_id: UUID,
    presentation_plan_id: UUID | None,
) -> dict:
    if presentation_plan_id is not None:
        plan = store.get_presentation_plan(
            presentation_plan_id=presentation_plan_id,
            user_id=user_id,
        )
        if plan["framework_version_id"] != framework_version_id:
            raise not_found(
                "PRESENTATION_PLAN_NOT_FOUND",
                f"Presentation plan {presentation_plan_id} was not found",
            )
        return plan

    plan = store.get_latest_presentation_plan(
        framework_version_id=framework_version_id,
        user_id=user_id,
    )
    if plan is None:
        raise bad_request(
            "PRESENTATION_PLAN_NOT_FOUND",
            "Generate a presentation plan before generating the presentation",
        )
    return plan


def enqueue_presentation_plan_generate(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_version_id: UUID | None,
):
    framework = _require_confirmed_framework(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_version_id=framework_version_id,
    )
    plan = store.generate_presentation_plan_stub(
        framework_version_id=framework["id"],
        user_id=user_id,
    )
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="presentation_planning",
    )
    return plan, job


def enqueue_presentation_generate(
    store: DataStore,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework_version_id: UUID | None,
    presentation_plan_id: UUID | None,
    name: str | None,
):
    framework = _require_confirmed_framework(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_version_id=framework_version_id,
    )
    plan = _resolve_presentation_plan(
        store,
        opportunity_id=opportunity_id,
        user_id=user_id,
        framework_version_id=framework["id"],
        presentation_plan_id=presentation_plan_id,
    )
    presentation = store.create_presentation(
        presentation_plan_id=plan["id"],
        user_id=user_id,
        name=name or str(plan["plan_json"].get("title") or "Presentation"),
    )
    store.create_presentation_version_with_slides(
        presentation_id=presentation["id"],
        user_id=user_id,
        plan_json=plan["plan_json"],
    )
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="presentation_generation",
        presentation_id=presentation["id"],
    )
    return presentation, plan, job


def enqueue_slide_regenerate(
    store: DataStore,
    *,
    presentation_id: UUID,
    slide_id: UUID,
    user_id: UUID,
):
    opportunity_id = store.get_presentation_opportunity_id(
        presentation_id=presentation_id,
        user_id=user_id,
    )
    slide = store.regenerate_slide(
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
    )
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="slide_regenerate",
        presentation_id=presentation_id,
    )
    return slide, job


def enqueue_slide_change_layout(
    store: DataStore,
    *,
    presentation_id: UUID,
    slide_id: UUID,
    user_id: UUID,
    layout_id: str,
):
    if layout_id not in VALID_LAYOUT_IDS:
        raise bad_request(
            "INVALID_LAYOUT_ID",
            f"layout_id must be a registered layout; got {layout_id}",
        )
    opportunity_id = store.get_presentation_opportunity_id(
        presentation_id=presentation_id,
        user_id=user_id,
    )
    slide = store.change_slide_layout(
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
        layout_id=layout_id,
    )
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="slide_change_layout",
        presentation_id=presentation_id,
    )
    return slide, job
