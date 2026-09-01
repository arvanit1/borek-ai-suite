"""Opportunity routes (AT-40 / AT-56 / v2 section 22.1)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.jobs import ActiveJobResponse
from app.schemas.opportunities import (
    OpportunityCreateRequest,
    OpportunityResponse,
    OpportunityUpdateRequest,
)
<<<<<<< Updated upstream
from app.services import job_service
from app.services.api_errors import not_found
=======
from app.schemas.jobs import JobResponse
from app.services import job_service
>>>>>>> Stashed changes
from app.services.audit import AuditAction, AuditObjectType, record_audit_event

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
