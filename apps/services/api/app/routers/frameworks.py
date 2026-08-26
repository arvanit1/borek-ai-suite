"""Framework routes (AT-41 / v2 section 22.2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.frameworks import (
    ConfirmFrameworkRequest,
    FrameworkGenerateResponse,
    FrameworkVersionResponse,
    RegenerateChapterRequest,
)
from app.schemas.jobs import JobEnqueueResponse
from app.services import framework_generation

router = APIRouter(dependencies=[Depends(get_current_user)])
opportunity_router = APIRouter(dependencies=[Depends(get_current_user)])


def _to_response(row: dict) -> FrameworkVersionResponse:
    return FrameworkVersionResponse.model_validate(row)


@router.get("/{framework_version_id}", response_model=FrameworkVersionResponse)
def get_framework_version(
    framework_version_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FrameworkVersionResponse:
    row = store.get_framework_version(
        framework_version_id=framework_version_id,
        user_id=user.id,
    )
    return _to_response(row)


@opportunity_router.get("/{opportunity_id}/framework", response_model=FrameworkVersionResponse)
def get_latest_framework(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FrameworkVersionResponse:
    row = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user.id)
    return _to_response(row)


@opportunity_router.post(
    "/{opportunity_id}/framework/generate",
    response_model=FrameworkGenerateResponse,
    status_code=202,
)
def generate_framework(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FrameworkGenerateResponse:
    framework_version, job = framework_generation.enqueue_framework_generate(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
    )
    return FrameworkGenerateResponse(
        job_id=str(job.id),
        status="queued",
        framework_version_id=framework_version["id"],
    )


@opportunity_router.post(
    "/{opportunity_id}/framework/regenerate-chapter",
    response_model=JobEnqueueResponse,
    status_code=202,
)
def regenerate_chapter(
    opportunity_id: UUID,
    body: RegenerateChapterRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> JobEnqueueResponse:
    _, job = framework_generation.enqueue_regenerate_chapter(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
        chapter_id=body.chapter_id,
    )
    return JobEnqueueResponse(job_id=str(job.id), status="queued")


@opportunity_router.post(
    "/{opportunity_id}/framework/confirm",
    response_model=FrameworkVersionResponse,
)
def confirm_framework(
    opportunity_id: UUID,
    body: ConfirmFrameworkRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FrameworkVersionResponse:
    row = framework_generation.confirm_framework(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
        framework_version_id=body.framework_version_id,
    )
    return _to_response(row)


@opportunity_router.post(
    "/{opportunity_id}/framework/render",
    response_model=JobEnqueueResponse,
    status_code=202,
)
def render_framework(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> JobEnqueueResponse:
    _, job = framework_generation.enqueue_framework_render(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
    )
    return JobEnqueueResponse(job_id=str(job.id), status="queued")
