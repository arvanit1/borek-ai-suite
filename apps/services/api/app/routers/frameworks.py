"""Framework routes (AT-41 / v2 section 22.2)."""

from __future__ import annotations

from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.frameworks import (
    ConfirmFrameworkRequest,
    FrameworkGenerateResponse,
    FrameworkVersionResponse,
    RegenerateChapterRequest,
    UpdateFrameworkRequest,
)
from app.schemas.jobs import JobEnqueueResponse
from app.services import framework_generation, job_service
from app.services.audit import AuditAction, AuditObjectType, record_audit_event

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


@router.get("/{framework_version_id}/render", response_model=None)
def download_framework_render(
    framework_version_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
    format: Literal["pdf", "html", "docx"] = Query(default="pdf"),
    lang: str = Query(default="en"),
) -> FileResponse | Response:
    row = store.get_framework_version(
        framework_version_id=framework_version_id,
        user_id=user.id,
    )
    payload = dict(row.get("framework_json") or {})
    payload["status"] = row.get("status") or payload.get("status") or "draft"
    payload.setdefault("version", row.get("version_number") or payload.get("version") or 1)
    language = "de" if str(lang).lower().startswith("de") else "en"

    if format == "pdf":
        cached = framework_generation.resolve_framework_render_path(
            framework_version_id, output_format="pdf"
        )
        if cached.is_file() and language == "en" and payload.get("status") == "confirmed":
            return FileResponse(
                cached,
                media_type="application/pdf",
                filename=f"{framework_version_id}-customer-report.pdf",
            )
        from app.services.framework_renderer import render_framework_pdf

        return Response(
            content=render_framework_pdf(payload, language=language),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="framework-{framework_version_id}.pdf"'
                )
            },
        )

    if format == "html":
        from app.services.framework_renderer import render_framework_html

        return Response(
            content=render_framework_html(payload, language=language),
            media_type="text/html; charset=utf-8",
        )

    from app.services.framework_renderer import render_framework_docx

    return Response(
        content=render_framework_docx(payload, language=language),
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="framework-{framework_version_id}.docx"'
            )
        },
    )


@opportunity_router.get("/{opportunity_id}/framework", response_model=FrameworkVersionResponse)
def get_latest_framework(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FrameworkVersionResponse:
    row = store.get_latest_framework(opportunity_id=opportunity_id, user_id=user.id)
    return _to_response(row)


@opportunity_router.get("/{opportunity_id}/framework/review")
def get_framework_review(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> dict:
    return framework_generation.get_framework_review(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
    )


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
    is_existing = bool(framework_version.get("existing"))
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FRAMEWORK_GENERATE,
        object_type=AuditObjectType.FRAMEWORK_VERSION,
        object_id=framework_version.get("id") or opportunity_id,
    )
    return FrameworkGenerateResponse(
        job_id=str(job.id),
        status=job_service.enqueue_status_for_job(job, existing=is_existing),
        is_existing_job=is_existing,
        framework_version_id=framework_version.get("id"),
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
    framework_version, job = framework_generation.enqueue_regenerate_chapter(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
        chapter_id=body.chapter_id,
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FRAMEWORK_REGENERATE_CHAPTER,
        object_type=AuditObjectType.FRAMEWORK_VERSION,
        object_id=framework_version["id"],
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
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FRAMEWORK_CONFIRM,
        object_type=AuditObjectType.FRAMEWORK_VERSION,
        object_id=row["id"],
    )
    return _to_response(row)


@opportunity_router.patch(
    "/{opportunity_id}/framework",
    response_model=FrameworkVersionResponse,
)
def update_framework(
    opportunity_id: UUID,
    body: UpdateFrameworkRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> FrameworkVersionResponse:
    row = framework_generation.update_framework(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
        framework_json=body.framework_json,
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FRAMEWORK_UPDATE,
        object_type=AuditObjectType.FRAMEWORK_VERSION,
        object_id=row["id"],
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
    framework_version, job = framework_generation.enqueue_framework_render(
        store,
        opportunity_id=opportunity_id,
        user_id=user.id,
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FRAMEWORK_RENDER,
        object_type=AuditObjectType.FRAMEWORK_VERSION,
        object_id=framework_version["id"],
    )
    return JobEnqueueResponse(job_id=str(job.id), status="queued")
