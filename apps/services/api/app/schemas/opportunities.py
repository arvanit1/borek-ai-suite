"""Opportunity API schemas (AT-40 / v2 §22.1)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClientContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=100)


class AdditionalClientInformation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_requirements: list[str] = Field(default_factory=list, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    contacts: list[ClientContact] = Field(default_factory=list, max_length=100)
    priorities: list[str] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def reject_blank_list_values(self) -> AdditionalClientInformation:
        for field_name in ("location_requirements", "constraints", "priorities"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} cannot contain blank values")
        return self


class OpportunityCreateRequest(BaseModel):
    client_name: str = Field(..., min_length=1)
    opportunity_name: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    language: str = Field(default="en", min_length=2, max_length=10)
    pii_redaction_enabled: bool = True
    additional_client_information: AdditionalClientInformation | None = None


class OpportunityUpdateRequest(BaseModel):
    client_name: str | None = Field(default=None, min_length=1)
    opportunity_name: str | None = Field(default=None, min_length=1)
    department: str | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    status: str | None = Field(default=None, min_length=1)
    pii_redaction_enabled: bool | None = None
    additional_client_information: AdditionalClientInformation | None = None


class OpportunityResponse(BaseModel):
    id: UUID
    client_name: str
    opportunity_name: str
    department: str
    language: str
    status: str
    pii_redaction_enabled: bool = True
    additional_client_information: AdditionalClientInformation | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ClientLogoMetadata(BaseModel):
    id: UUID
    opportunity_id: UUID
    file_name: str
    mime_type: str
    size_bytes: int
    width_px: int | None = None
    height_px: int | None = None
    uploaded_at: datetime


class FiledArtifactResponse(BaseModel):
    idempotency_key: str
    opportunity_id: UUID
    presentation_id: UUID
    presentation_version_id: UUID
    framework_version_id: UUID
    artifact_kind: str
    content_type: str
    provider: str
    destination_path: str
    repository_ref: str | None = None
    status: str
    approved_by: UUID
    approved_at: datetime
    corpus_versions: list[str] = Field(default_factory=list)
    filed_at: datetime | None = None
    error_code: str | None = None
    error_retryable: bool | None = None
    updated_at: datetime | None = None
