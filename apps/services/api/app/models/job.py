"""SQLAlchemy models — generation_jobs (AT-36 / v2 §23)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GenerationJob(Base):
    """Maps to generation_jobs table (migration 009)."""

    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    presentation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("presentations.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="QUEUED")
    current_stage: Mapped[str] = mapped_column(String, nullable=False, default="QUEUED")
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
