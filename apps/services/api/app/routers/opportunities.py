"""Opportunity routes (AT-40 / AT-56 / v2 section 22.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.jobs import ActiveJobResponse, JobResponse
from app.schemas.opportunities import (
    ClientLogoMetadata,
    FiledArtifactResponse,
    OpportunityCreateRequest,
    OpportunityResponse,
    OpportunityUpdateRequest,
)
from app.services import job_service
from app.services.api_errors import not_found
from app.services.audit import AuditAction, AuditObjectType, record_audit_event
from app.services.client_logos import MAX_CLIENT_LOGO_BYTES, validate_client_logo

router = APIRouter(dependencies=[Depends(get_current_user)])


def _to_response(row: dict) -> OpportunityResponse:
    return OpportunityResponse.model_validate(row)


@router.post("", response_model=OpportunityResponse, status_code=201)
def create_opportunity(
    body: OpportunityCreateRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> OpportunityResponse:
    row = store.create_opportunity(
        user_id=user.id,
        client_name=body.client_name,
        opportunity_name=body.opportunity_name,
        department=body.department,
        language=body.language,
        pii_redaction_enabled=body.pii_redaction_enabled,
        additional_client_information=(
            body.additional_client_information.model_dump()
            if body.additional_client_information is not None
            else None
        ),
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.OPPORTUNITY_CREATE,
        object_type=AuditObjectType.OPPORTUNITY,
        object_id=row["id"],
    )
    return _to_response(row)


@router.get("", response_model=list[OpportunityResponse])
def list_opportunities(user: AuthUserDep, store: DataStoreDep) -> list[OpportunityResponse]:
    rows = store.list_opportunities(user_id=user.id)
    return [_to_response(row) for row in rows]


@router.put("/{opportunity_id}/client-logo", response_model=ClientLogoMetadata)
async def upload_or_replace_client_logo(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
    file: UploadFile = File(...),
) -> ClientLogoMetadata:
    file_name = (file.filename or "client-logo").replace("\\", "/").rsplit("/", 1)[-1]
    content = await file.read(MAX_CLIENT_LOGO_BYTES + 1)
    validated = validate_client_logo(file_name, file.content_type, content)
    storage_path = (
        f"{opportunity_id}/client-logo/{uuid4()}{Path(file_name).suffix.lower()}"
    )
    row, replaced = store.upsert_client_logo(
        opportunity_id=opportunity_id,
        user_id=user.id,
        file_name=file_name,
        mime_type=validated.mime_type,
        size_bytes=len(content),
        width_px=validated.width_px,
        height_px=validated.height_px,
        storage_path=storage_path,
        content=content,
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=(
            AuditAction.CLIENT_LOGO_REPLACE
            if replaced
            else AuditAction.CLIENT_LOGO_UPLOAD
        ),
        object_type=AuditObjectType.CLIENT_LOGO,
        object_id=row["id"],
    )
    return ClientLogoMetadata.model_validate(row)


@router.get("/{opportunity_id}/client-logo/content")
def get_client_logo_content(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> Response:
    row = store.get_client_logo(opportunity_id=opportunity_id, user_id=user.id)
    content = store.get_client_logo_content(
        opportunity_id=opportunity_id,
        user_id=user.id,
    )
    safe_name = str(row["file_name"]).replace('"', "")
    return Response(
        content=content,
        media_type=str(row["mime_type"]),
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{opportunity_id}/client-logo", response_model=ClientLogoMetadata)
def get_client_logo_metadata(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> ClientLogoMetadata:
    row = store.get_client_logo(opportunity_id=opportunity_id, user_id=user.id)
    return ClientLogoMetadata.model_validate(row)


@router.delete("/{opportunity_id}/client-logo", status_code=204)
def delete_client_logo(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> None:
    row = store.delete_client_logo(opportunity_id=opportunity_id, user_id=user.id)
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.CLIENT_LOGO_DELETE,
        object_type=AuditObjectType.CLIENT_LOGO,
        object_id=row["id"],
    )


@router.get("/{opportunity_id}/filed-artifacts", response_model=list[FiledArtifactResponse])
def list_filed_artifacts(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> list[FiledArtifactResponse]:
    rows = store.list_filed_artifacts(opportunity_id=opportunity_id, user_id=user.id)
    return [FiledArtifactResponse.model_validate(row) for row in rows]


@router.get("/{opportunity_id}/jobs/active", response_model=ActiveJobResponse)
def get_active_job(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
    stage_group: Literal["framework", "presentation"] | None = Query(default=None),
) -> ActiveJobResponse:
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user.id)
    row = store.get_active_job_for_opportunity(opportunity_id, stage_group)
    if row is None:
        raise not_found(
            "ACTIVE_JOB_NOT_FOUND",
            f"No job found for opportunity {opportunity_id}",
        )
    job = job_service.get_job(row["id"], repository=store)
    if job is None:
        raise not_found(
            "ACTIVE_JOB_NOT_FOUND",
            f"No job found for opportunity {opportunity_id}",
        )
    payload = job_service.job_to_response(job)
    return ActiveJobResponse(
        job_id=payload.job_id,
        job_type=payload.job_type,
        status=payload.status,
        current_stage=payload.current_stage,
        started_at=payload.started_at,
        error=payload.error,
    )


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> OpportunityResponse:
    row = store.get_opportunity(opportunity_id=opportunity_id, user_id=user.id)
    return _to_response(row)


@router.get("/{opportunity_id}/jobs/latest", response_model=JobResponse | None)
def get_latest_opportunity_job(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> JobResponse | None:
    store.get_opportunity(opportunity_id=opportunity_id, user_id=user.id)
    job = job_service.get_latest_job_for_opportunity(opportunity_id, repository=store)
    return job_service.job_to_response(job) if job is not None else None


@router.patch("/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(
    opportunity_id: UUID,
    body: OpportunityUpdateRequest,
    user: AuthUserDep,
    store: DataStoreDep,
) -> OpportunityResponse:
    row = store.update_opportunity(
        opportunity_id=opportunity_id,
        user_id=user.id,
        updates=body.model_dump(exclude_unset=True),
    )
    record_audit_event(
        store,
        actor_id=user.id,
        action=AuditAction.OPPORTUNITY_UPDATE,
        object_type=AuditObjectType.OPPORTUNITY,
        object_id=opportunity_id,
    )
    return _to_response(row)
