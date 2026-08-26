"""Framework API schemas (AT-41 / v2 §22.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.jobs import JobEnqueueResponse


class FrameworkVersionResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    version_number: int
    status: str
    framework_json: dict[str, Any]
    created_by: UUID
    created_at: datetime


class RegenerateChapterRequest(BaseModel):
    chapter_id: str = Field(..., pattern=r"^(?:[0-9]|1[0-3])$")


class ConfirmFrameworkRequest(BaseModel):
    framework_version_id: UUID | None = None


class FrameworkGenerateResponse(JobEnqueueResponse):
    framework_version_id: UUID | None = None
