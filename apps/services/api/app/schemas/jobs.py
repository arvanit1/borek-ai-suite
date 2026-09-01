"""Job API schemas — stage state machine and response models (AT-36)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStage(str, Enum):
    QUEUED = "QUEUED"
    TRANSCRIPT_PROCESSING = "TRANSCRIPT_PROCESSING"
    KNOWLEDGE_EXTRACTING = "KNOWLEDGE_EXTRACTING"
    FRAMEWORK_SYNTHESIZING = "FRAMEWORK_SYNTHESIZING"
    FRAMEWORK_VALIDATING = "FRAMEWORK_VALIDATING"
    PRESENTATION_PLANNING = "PRESENTATION_PLANNING"
    SLIDE_GENERATING = "SLIDE_GENERATING"
    SLIDE_VALIDATING = "SLIDE_VALIDATING"
    PPTX_RENDERING = "PPTX_RENDERING"
    PREVIEW_RENDERING = "PREVIEW_RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Ordered pipeline stages — advance_stage() moves one step at a time (v2 §24).
JOB_PIPELINE_STAGES: tuple[JobStage, ...] = (
    JobStage.QUEUED,
    JobStage.TRANSCRIPT_PROCESSING,
    JobStage.KNOWLEDGE_EXTRACTING,
    JobStage.FRAMEWORK_SYNTHESIZING,
    JobStage.FRAMEWORK_VALIDATING,
    JobStage.PRESENTATION_PLANNING,
    JobStage.SLIDE_GENERATING,
    JobStage.SLIDE_VALIDATING,
    JobStage.PPTX_RENDERING,
    JobStage.PREVIEW_RENDERING,
)


class JobErrorDetail(BaseModel):
    code: str
    message: str
    stage: JobStage
    retryable: bool


class JobResponse(BaseModel):
    job_id: str
    job_type: str
    status: JobStatus
    current_stage: JobStage
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: JobErrorDetail | None = None
    result: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)


class JobEnqueueResponse(BaseModel):
    job_id: str
    status: str = Field(default="queued")
    is_existing_job: bool = False


class ActiveJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: JobStatus
    current_stage: JobStage
    started_at: datetime | None = None
    error: JobErrorDetail | None = None
