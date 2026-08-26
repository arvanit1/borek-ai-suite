"""Transcript routes (AT-40 / v2 section 22.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.transcripts import TranscriptResponse, TranscriptUploadResponse
from app.services.data.supabase_store import validate_transcript_upload

router = APIRouter(dependencies=[Depends(get_current_user)])


def _to_response(row: dict) -> TranscriptResponse:
    return TranscriptResponse.model_validate(row)


@router.post("/{opportunity_id}/transcripts", response_model=TranscriptUploadResponse, status_code=201)
async def upload_transcript(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
    file: UploadFile = File(...),
) -> TranscriptUploadResponse:
    file_name = file.filename or "upload.txt"
    validate_transcript_upload(file_name, file.content_type)
    storage_path = f"transcripts/{opportunity_id}/{uuid4()}{Path(file_name).suffix.lower()}"
    row = store.create_transcript(
        opportunity_id=opportunity_id,
        user_id=user.id,
        file_name=file_name,
        mime_type=file.content_type or "text/plain",
        storage_path=storage_path,
    )
    transcript = _to_response(row)
    return TranscriptUploadResponse(
        transcript=transcript,
        processing_status=transcript.processing_status,
    )


@router.get("/{opportunity_id}/transcripts", response_model=list[TranscriptResponse])
def list_transcripts(
    opportunity_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> list[TranscriptResponse]:
    rows = store.list_transcripts(opportunity_id=opportunity_id, user_id=user.id)
    return [_to_response(row) for row in rows]


@router.get("/{opportunity_id}/transcripts/{transcript_id}", response_model=TranscriptResponse)
def get_transcript(
    opportunity_id: UUID,
    transcript_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> TranscriptResponse:
    row = store.get_transcript(
        opportunity_id=opportunity_id,
        transcript_id=transcript_id,
        user_id=user.id,
    )
    return _to_response(row)


@router.post(
    "/{opportunity_id}/transcripts/{transcript_id}/regenerate",
    response_model=TranscriptResponse,
)
def regenerate_transcript(
    opportunity_id: UUID,
    transcript_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> TranscriptResponse:
    row = store.regenerate_transcript(
        opportunity_id=opportunity_id,
        transcript_id=transcript_id,
        user_id=user.id,
    )
    return _to_response(row)
