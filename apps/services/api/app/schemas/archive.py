"""Public in-app archive contract for AT-61/MS-29."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ArchiveArtifactResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    presentation_id: UUID
    presentation_version_id: UUID
    artifact_kind: str
    content_type: str
    file_name: str
    size_bytes: int
    sha256: str
    status: str
    client_name: str
    opportunity_name: str
    approved_by: UUID
    approved_at: datetime
    filed_at: datetime | None = None
    corpus_versions: list[str] = Field(default_factory=list)
    journey_stage: str | None = None
    prior_stage_presentation_version_id: UUID | None = None
    demo_marker: str | None = None
    download_url: str | None = None
