"""Opportunity routes (AT-40 / v2 section 22.1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.opportunities import (
    OpportunityCreateRequest,
    OpportunityResponse,
    OpportunityUpdateRequest,
)

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
    )
    return _to_response(row)


@router.get("", response_model=list[OpportunityResponse])
def list_opportunities(user: AuthUserDep, store: DataStoreDep) -> list[OpportunityResponse]:
    rows = store.list_opportunities(user_id=user.id)
    return [_to_response(row) for row in rows]


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> OpportunityResponse:
    row = store.get_opportunity(opportunity_id=opportunity_id, user_id=user.id)
    return _to_response(row)


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
    return _to_response(row)
