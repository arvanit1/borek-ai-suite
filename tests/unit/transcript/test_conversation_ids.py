"""ES-3 — stable opportunity / transcript / conversation ids."""

from __future__ import annotations

import uuid

import pytest

from services.transcript.conversation_ids import (
    TranscriptIdentityError,
    allocate_opportunity_id,
    allocate_transcript_identity,
    next_conversation_id,
)


def test_new_opportunity_id_is_unique_uuid() -> None:
    first = allocate_opportunity_id()
    second = allocate_opportunity_id()
    uuid.UUID(first)
    uuid.UUID(second)
    assert first != second


def test_existing_opportunity_id_is_reused() -> None:
    original = allocate_opportunity_id()
    assert allocate_opportunity_id(original) == original


def test_first_transcript_is_c1() -> None:
    opportunity_id = allocate_opportunity_id()
    tagged = allocate_transcript_identity(opportunity_id)
    assert tagged.opportunity_id == opportunity_id
    assert tagged.conversation_id == "C1"
    uuid.UUID(tagged.transcript_id)


def test_second_transcript_gets_next_conversation_id() -> None:
    opportunity_id = allocate_opportunity_id()
    first = allocate_transcript_identity(opportunity_id)
    second = allocate_transcript_identity(
        opportunity_id,
        taken_conversation_ids=[first.conversation_id],
    )
    assert second.conversation_id == "C2"
    assert second.transcript_id != first.transcript_id
    assert second.opportunity_id == first.opportunity_id


def test_regeneration_reuses_all_ids() -> None:
    opportunity_id = allocate_opportunity_id()
    original = allocate_transcript_identity(opportunity_id)
    regenerated = allocate_transcript_identity(
        original.opportunity_id,
        transcript_id=original.transcript_id,
        conversation_id=original.conversation_id,
        taken_conversation_ids=[],
    )
    assert regenerated == original


def test_next_conversation_id_uses_max_plus_one() -> None:
    assert next_conversation_id(["C1", "C3"]) == "C4"


def test_duplicate_conversation_id_is_rejected() -> None:
    opportunity_id = allocate_opportunity_id()
    with pytest.raises(TranscriptIdentityError) as exc_info:
        allocate_transcript_identity(
            opportunity_id,
            conversation_id="C1",
            taken_conversation_ids=["C1"],
        )
    assert "already used" in exc_info.value.user_message


def test_invalid_existing_opportunity_id_is_rejected() -> None:
    with pytest.raises(TranscriptIdentityError):
        allocate_opportunity_id("not-a-uuid")
