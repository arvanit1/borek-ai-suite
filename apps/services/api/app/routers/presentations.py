"""Presentation routes (AT-42 / AT-43 / AT-44 / v2 section 22.3–22.4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.presentations import (
    ChangeSlideLayoutRequest,
    GeneratePresentationPlanRequest,
    GeneratePresentationRequest,
    PresentationGenerateResponse,
    PresentationPlanGenerateResponse,
    PresentationPlanResponse,
    PresentationResponse,
    SlideResponse,
)
from app.schemas.jobs import JobEnqueueResponse
from app.services import presentation_generation

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
    presentation, plan, job = presentation_generation.enqueue_presentation_generate(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
        framework_version_id=body.framework_version_id,
        presentation_plan_id=body.presentation_plan_id,
        name=body.name,
    )
    return PresentationGenerateResponse(
        job_id=str(job.id),
        status="queued",
        presentation_id=presentation["id"],
        presentation_plan_id=plan["id"],
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
    _, job = presentation_generation.enqueue_slide_regenerate(
        store,
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user.id,
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
    _, job = presentation_generation.enqueue_slide_change_layout(
        store,
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user.id,
        layout_id=body.layout_id,
    )
    return JobEnqueueResponse(job_id=str(job.id), status="queued")


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
