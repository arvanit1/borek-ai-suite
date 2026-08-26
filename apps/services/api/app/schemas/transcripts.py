"""Transcript API schemas (AT-40 / v2 §22.1)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TranscriptResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    file_name: str
    mime_type: str
    storage_path: str
    processing_status: str
    created_at: datetime


class TranscriptUploadResponse(BaseModel):
    transcript: TranscriptResponse
    processing_status: str
