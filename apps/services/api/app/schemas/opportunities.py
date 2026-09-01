"""Opportunity API schemas (AT-40 / v2 §22.1)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OpportunityCreateRequest(BaseModel):
    client_name: str = Field(..., min_length=1)
    opportunity_name: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    language: str = Field(default="en", min_length=2, max_length=10)
    pii_redaction_enabled: bool = True


class OpportunityUpdateRequest(BaseModel):
    client_name: str | None = Field(default=None, min_length=1)
    opportunity_name: str | None = Field(default=None, min_length=1)
    department: str | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    status: str | None = Field(default=None, min_length=1)
    pii_redaction_enabled: bool | None = None


class OpportunityResponse(BaseModel):
    id: UUID
    client_name: str
    opportunity_name: str
    department: str
    language: str
    status: str
    pii_redaction_enabled: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime
