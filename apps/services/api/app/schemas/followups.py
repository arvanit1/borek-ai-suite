"""BT-33 / MS-32 follow-up API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FollowupGenerateRequest(BaseModel):
    transcript_id: str
    project_key: str = Field(min_length=1)
    project_statics: dict
    calendar_meeting_date: str | None = None
    attachment_name: str | None = None
    client_recipient_email: str | None = None
    meeting_owner_email: str = Field(min_length=3)


class FollowupDraftResponse(BaseModel):
    id: str
    opportunity_id: str
    job_id: str
    subject: str
    body: str
    review_flags: list[str]
    attachment_name: str | None = None
    status: Literal["draft", "reviewed", "sent", "sent_unknown"]
    provider_draft_id: str | None = None
    reviewed_at: datetime | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FollowupDraftUpdateRequest(BaseModel):
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


class FollowupReviewConfirmResponse(BaseModel):
    draft: FollowupDraftResponse
    provider_draft_id: str | None = None


class FollowupDeliveryRecordRequest(BaseModel):
    final_subject: str | None = None
    final_body: str | None = None
    delivery_status: Literal["sent", "sent_unknown"]
