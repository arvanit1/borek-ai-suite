"""Presentation planning/generation orchestration (AT-42 / AT-43).

HTTP handlers only enqueue jobs. Workers invoke the owner planner and Group A/B/C
generators, then render validated artifacts. EXECUTIVE_SUMMARY_01 stays fail-closed.
"""

from __future__ import annotations

import uuid
from uuid import UUID

from app.config import settings
from app.schemas.presentations import LAYOUT_REGISTRY, VALID_LAYOUT_IDS
from app.services import job_service
from app.services.api_errors import bad_request, not_found
from app.services.data import DataStore
from app.services.renderer_client import render_deck_assets
from app.services.stage_b_orchestration import plan_json_from_confirmed_framework
from app.services.stage_b_providers import install_runtime_stage_b_providers


def _dispatch_task(task, *args: str) -> None:
    if settings.API_DATA_BACKEND == "memory":
        task.run(*args)
    else:
        task.delay(*args)


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
    plan_id = uuid.uuid4()
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="presentation_planning",
        repository=store,
    )
    from app.worker import run_presentation_planning_task

    _dispatch_task(
        run_presentation_planning_task,
        str(job.id),
        str(framework["id"]),
        str(user_id),
        str(plan_id),
    )
    return {"id": plan_id}, job


def execute_presentation_planning(
    store: DataStore,
    *,
    framework_version_id: UUID,
    user_id: UUID,
    presentation_plan_id: UUID,
) -> dict:
    install_runtime_stage_b_providers()
    framework = store.get_framework_version(
        framework_version_id=framework_version_id,
        user_id=user_id,
    )
    plan_json = plan_json_from_confirmed_framework(framework["framework_json"])
    return store.create_presentation_plan(
        framework_version_id=framework_version_id,
        user_id=user_id,
        plan_json=plan_json,
        presentation_plan_id=presentation_plan_id,
    )


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
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="presentation_generation",
        presentation_id=presentation["id"],
        repository=store,
    )
    from app.worker import run_presentation_generation_task

    _dispatch_task(
        run_presentation_generation_task,
        str(job.id),
        str(presentation["id"]),
        str(user_id),
    )
    return presentation, plan, job


def execute_presentation_generation(
    store: DataStore,
    *,
    presentation_id: UUID,
    user_id: UUID,
) -> tuple[dict, dict]:
    install_runtime_stage_b_providers()
    presentation = store.get_presentation(presentation_id=presentation_id, user_id=user_id)
    plan = store.get_presentation_plan(
        presentation_plan_id=presentation["presentation_plan_id"],
        user_id=user_id,
    )
    version = store.create_presentation_version_with_slides(
        presentation_id=presentation_id,
        user_id=user_id,
        plan_json=plan["plan_json"],
    )
    return version, plan


def render_presentation_version(
    store: DataStore,
    *,
    version: dict,
    plan: dict,
) -> dict:
    if settings.RENDERER_EXECUTION_MODE != "live":
        return version
    assets = render_deck_assets(
        version_id=version["id"],
        presentation_plan=plan["plan_json"],
        slide_specs=version["slides_json"],
    )
    updated = store.update_presentation_version_assets(
        presentation_version_id=version["id"],
        assets=assets,
        status="ready",
    )
    updated["storage_size_bytes"] = int(assets.get("storage_size_bytes") or 0)
    return updated


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
    slide = store.get_slide(
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
    )
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="slide_regenerate",
        presentation_id=presentation_id,
        repository=store,
    )
    from app.worker import run_slide_regenerate_task

    _dispatch_task(
        run_slide_regenerate_task,
        str(job.id),
        str(presentation_id),
        str(slide_id),
        str(user_id),
    )
    return slide, job


def execute_slide_regenerate(
    store: DataStore,
    *,
    presentation_id: UUID,
    slide_id: UUID,
    user_id: UUID,
) -> dict:
    install_runtime_stage_b_providers()
    return store.regenerate_slide(
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
    )


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
    current = store.get_slide(
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
    )
    current_category = LAYOUT_REGISTRY[current["layout_id"]]["category"]
    target_category = LAYOUT_REGISTRY[layout_id]["category"]
    if current_category != target_category:
        raise bad_request(
            "LAYOUT_CATEGORY_MISMATCH",
            "A slide can only change to another layout in the same category",
        )
    opportunity_id = store.get_presentation_opportunity_id(
        presentation_id=presentation_id,
        user_id=user_id,
    )
    slide = current
    job = job_service.create_job(
        opportunity_id=opportunity_id,
        job_type="slide_change_layout",
        presentation_id=presentation_id,
        repository=store,
    )
    from app.worker import run_slide_change_layout_task

    _dispatch_task(
        run_slide_change_layout_task,
        str(job.id),
        str(presentation_id),
        str(slide_id),
        str(user_id),
        layout_id,
    )
    return slide, job


def execute_slide_change_layout(
    store: DataStore,
    *,
    presentation_id: UUID,
    slide_id: UUID,
    user_id: UUID,
    layout_id: str,
) -> dict:
    install_runtime_stage_b_providers()
    return store.change_slide_layout(
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
        layout_id=layout_id,
    )
