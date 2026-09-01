"""Presentation routes (AT-42 / AT-43 / AT-44 / v2 section 22.3–22.4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.presentations import (
    ChangeSlideLayoutRequest,
    DeckCenterResponse,
    GeneratePresentationPlanRequest,
    GeneratePresentationRequest,
    PresentationGenerateResponse,
    PresentationPlanGenerateResponse,
    PresentationPlanResponse,
    PresentationResponse,
    SlideResponse,
)
from app.schemas.jobs import JobEnqueueResponse
from app.services import deck_center, job_service, presentation_generation
from app.services.audit import AuditAction, AuditObjectType, record_audit_event
from app.services.renderer_client import RendererClientError

router = APIRouter(dependencies=[Depends(get_current_user)])
opportunity_router = APIRouter(dependencies=[Depends(get_current_user)])
plan_router = APIRouter(dependencies=[Depends(get_current_user)])


def _plan_response(row: dict) -> PresentationPlanResponse:
    return PresentationPlanResponse.model_validate(row)


def _presentation_response(row: dict) -> PresentationResponse:
    return PresentationResponse.model_validate(row)


def _slide_response(row: dict) -> SlideResponse:
    return SlideResponse.model_validate(row)


@router.get("", response_model=list[PresentationResponse])
def list_presentations(user: AuthUserDep, store: DataStoreDep) -> list[PresentationResponse]:
    rows = store.list_presentations(user_id=user.id)
    return [_presentation_response(row) for row in rows]


@router.get("/{presentation_id}", response_model=PresentationResponse)
def get_presentation(
    presentation_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> PresentationResponse:
    row = store.get_presentation(presentation_id=presentation_id, user_id=user.id)
    return _presentation_response(row)


@plan_router.get("/{presentation_plan_id}", response_model=PresentationPlanResponse)
def get_presentation_plan(
    presentation_plan_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> PresentationPlanResponse:
    row = store.get_presentation_plan(
        presentation_plan_id=presentation_plan_id,
        user_id=user.id,
    )
    return _plan_response(row)


@opportunity_router.get(
    "/{opportunity_id}/presentation",
    response_model=PresentationResponse,
)
def get_latest_presentation_for_opportunity(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> PresentationResponse:
    row = store.get_latest_presentation_for_opportunity(
        opportunity_id=opportunity_id,
        user_id=user.id,
    )
    return _presentation_response(row)


@opportunity_router.get(
    "/{opportunity_id}/presentation-plan",
    response_model=PresentationPlanResponse,
)
def get_latest_presentation_plan(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> PresentationPlanResponse:
    row = store.get_latest_presentation_plan_for_opportunity(
        opportunity_id=opportunity_id,
        user_id=user.id,
    )
    return _plan_response(row)


@opportunity_router.post(
    "/{opportunity_id}/presentation-plan/generate",
    response_model=PresentationPlanGenerateResponse,
    status_code=202,
)
def generate_presentation_plan(
    opportunity_id: UUID,
    body: GeneratePresentationPlanRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> PresentationPlanGenerateResponse:
    plan, job = presentation_generation.enqueue_presentation_plan_generate(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
        framework_version_id=body.framework_version_id,
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.PRESENTATION_PLAN_GENERATE,
        object_type=AuditObjectType.PRESENTATION_PLAN,
        object_id=plan["id"],
    )
    return PresentationPlanGenerateResponse(
        job_id=str(job.id),
        status="queued",
        presentation_plan_id=plan["id"],
    )


@opportunity_router.post(
    "/{opportunity_id}/presentation/generate",
    response_model=PresentationGenerateResponse,
    status_code=202,
)
def generate_presentation(
    opportunity_id: UUID,
    body: GeneratePresentationRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> PresentationGenerateResponse:
    try:
        presentation, plan, job, is_existing = presentation_generation.enqueue_presentation_generate(
            store,
            opportunity_id=opportunity_id,
            user_id=user.id,
            framework_version_id=body.framework_version_id,
            presentation_plan_id=body.presentation_plan_id,
            name=body.name,
        )
    except RendererClientError as exc:
        status_code = 503 if exc.retryable else 422
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.PRESENTATION_GENERATE,
        object_type=AuditObjectType.PRESENTATION,
        object_id=presentation.get("id") or opportunity_id,
    )
    return PresentationGenerateResponse(
        job_id=str(job.id),
        status=job_service.enqueue_status_for_job(job, existing=is_existing),
        is_existing_job=is_existing,
        presentation_id=presentation.get("id"),
        presentation_plan_id=plan.get("id"),
    )


@router.post(
    "/{presentation_id}/slides/{slide_id}/regenerate",
    response_model=JobEnqueueResponse,
    status_code=202,
)
def regenerate_slide(
    presentation_id: UUID,
    slide_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> JobEnqueueResponse:
    slide, job = presentation_generation.enqueue_slide_regenerate(
        store,
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user.id,
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.SLIDE_REGENERATE,
        object_type=AuditObjectType.SLIDE,
        object_id=slide["id"],
    )
    return JobEnqueueResponse(job_id=str(job.id), status="queued")


@router.post(
    "/{presentation_id}/slides/{slide_id}/change-layout",
    response_model=JobEnqueueResponse,
    status_code=202,
)
def change_slide_layout(
    presentation_id: UUID,
    slide_id: UUID,
    body: ChangeSlideLayoutRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> JobEnqueueResponse:
    slide, job = presentation_generation.enqueue_slide_change_layout(
        store,
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user.id,
        layout_id=body.layout_id,
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.SLIDE_CHANGE_LAYOUT,
        object_type=AuditObjectType.SLIDE,
        object_id=slide["id"],
    )
    return JobEnqueueResponse(job_id=str(job.id), status="queued")


@router.get("/{presentation_id}/deck", response_model=DeckCenterResponse)
def get_deck_center(
    presentation_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> DeckCenterResponse:
    payload = deck_center.build_deck_center_payload(
        store,
        presentation_id=presentation_id,
        user_id=user.id,
    )
    return DeckCenterResponse.model_validate(payload)


@router.get("/{presentation_id}/preview/slides/{slide_index}.png")
def get_slide_preview_image(
    presentation_id: UUID,
    slide_index: int,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FileResponse:
    path = deck_center.resolve_deck_preview_image_path(
        store,
        presentation_id=presentation_id,
        user_id=user.id,
        slide_index=slide_index,
    )
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.get("/{presentation_id}/download/pptx")
def download_presentation_pptx(
    presentation_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FileResponse:
    path = deck_center.resolve_deck_file_path(
        store,
        presentation_id=presentation_id,
        user_id=user.id,
        kind="pptx",
    )
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{presentation_id}.pptx",
    )


@router.get("/{presentation_id}/download/pdf")
def download_presentation_pdf(
    presentation_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FileResponse:
    path = deck_center.resolve_deck_file_path(
        store,
        presentation_id=presentation_id,
        user_id=user.id,
        kind="pdf",
    )
    return FileResponse(path, media_type="application/pdf", filename=f"{presentation_id}.pdf")


@router.get("/{presentation_id}/slides", response_model=list[SlideResponse])
def list_slides(
    presentation_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> list[SlideResponse]:
    rows = store.list_slides(presentation_id=presentation_id, user_id=user.id)
    return [_slide_response(row) for row in rows]


@router.get("/{presentation_id}/slides/{slide_id}", response_model=SlideResponse)
def get_slide(
    presentation_id: UUID,
    slide_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> SlideResponse:
    row = store.get_slide(
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user.id,
    )
    return _slide_response(row)
