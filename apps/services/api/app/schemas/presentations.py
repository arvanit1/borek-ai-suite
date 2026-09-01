"""Presentation API schemas (AT-42 / AT-43 / AT-44 / v2 section 22.3–22.4)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.jobs import JobEnqueueResponse

_LAYOUT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[5]
    / "packages"
    / "contracts"
    / "layout_registry.json"
)
LAYOUT_REGISTRY = json.loads(_LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8"))["layouts"]
VALID_LAYOUT_IDS = frozenset(LAYOUT_REGISTRY.keys())


class GeneratePresentationPlanRequest(BaseModel):
    framework_version_id: UUID | None = None


class GeneratePresentationRequest(BaseModel):
    framework_version_id: UUID | None = None
    presentation_plan_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)


class PresentationPlanResponse(BaseModel):
    id: UUID
    framework_version_id: UUID
    plan_json: dict[str, Any]
    created_at: datetime


class PresentationResponse(BaseModel):
    id: UUID
    presentation_plan_id: UUID
    name: str
    status: str
    created_at: datetime


class PresentationPlanGenerateResponse(JobEnqueueResponse):
    presentation_plan_id: UUID


class PresentationGenerateResponse(JobEnqueueResponse):
    presentation_id: UUID | None = None
    presentation_plan_id: UUID | None = None


class ChangeSlideLayoutRequest(BaseModel):
    layout_id: str = Field(..., min_length=1)


class SlideResponse(BaseModel):
    id: UUID
    presentation_version_id: UUID
    slide_index: int
    layout_id: str
    slide_spec: dict[str, Any]
    source_chapter_ids: list[str]
    created_at: datetime


class DeckSlidePreviewResponse(BaseModel):
    slide_id: UUID
    slide_index: int
    layout_id: str
    preview_url: str


class DeckCenterResponse(BaseModel):
    presentation_id: UUID
    presentation_name: str
    version_number: int
    status: str
    slides: list[DeckSlidePreviewResponse]
    pptx_download_url: str
    pdf_download_url: str
