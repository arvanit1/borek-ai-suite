"""Framework routes (AT-41 / v2 section 22.2)."""

from __future__ import annotations

from uuid import UUID

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
from app.services import framework_generation
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
    format: str = Query(default="pdf"),
) -> FileResponse | Response:
    if format not in {"pdf", "docx"}:
        from app.services.api_errors import bad_request

        raise bad_request(
            "UNSUPPORTED_FRAMEWORK_FORMAT",
            "Supported framework export formats are pdf and docx",
        )
    row = store.get_framework_version(framework_version_id=framework_version_id, user_id=user.id)
    if format == "docx":
        from services.framework.rendering.customer_docx import render_customer_docx
        from services.framework.eligibility import RenderBlocked

        try:
            docx_bytes = render_customer_docx(row["framework_json"])
        except RenderBlocked as exc:
            from app.services.api_errors import bad_request

            raise bad_request("FRAMEWORK_RENDER_BLOCKED", exc.user_message) from exc
        filename = f"{framework_version_id}-customer-report.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    path = framework_generation.resolve_framework_render_path(framework_version_id, output_format="pdf")
    if not path.is_file():
        from app.services.api_errors import not_found

        raise not_found("FRAMEWORK_RENDER_NOT_FOUND", "Framework PDF is not ready")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{framework_version_id}-customer-report.pdf",
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
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.FRAMEWORK_GENERATE,
        object_type=AuditObjectType.FRAMEWORK_VERSION,
        object_id=framework_version["id"],
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
