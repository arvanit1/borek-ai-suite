"""ES-3 — stable opportunity, transcript, and conversation ids.

Ids are minted once at upload and reused on regenerate. Conversation ids follow
the FrameworkObject source_ref convention (C1, C2, …).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Sequence

CONVERSATION_ID_RE = re.compile(r"^C([1-9][0-9]*)$")


class TranscriptIdentityError(ValueError):
    """Invalid or colliding identity. ``user_message`` is safe for the client."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True, slots=True)
class TranscriptIdentity:
    opportunity_id: str
    transcript_id: str
    conversation_id: str


def allocate_opportunity_id(existing: str | None = None) -> str:
    if existing is None or not existing.strip():
        return _new_uuid()
    return _require_uuid(existing.strip(), field="opportunity_id")


def allocate_transcript_identity(
    opportunity_id: str,
    *,
    transcript_id: str | None = None,
    conversation_id: str | None = None,
    taken_conversation_ids: Sequence[str] = (),
) -> TranscriptIdentity:
    """Return ids for one uploaded transcript.

    Pass previously stored ids to keep them unchanged across regeneration.
    """
    stable_opportunity_id = allocate_opportunity_id(opportunity_id)
    taken = tuple(item.strip() for item in taken_conversation_ids if item and item.strip())

    if transcript_id is None or not transcript_id.strip():
        stable_transcript_id = _new_uuid()
    else:
        stable_transcript_id = _require_uuid(transcript_id.strip(), field="transcript_id")

    if conversation_id is None or not conversation_id.strip():
        stable_conversation_id = next_conversation_id(taken)
    else:
        stable_conversation_id = _require_conversation_id(conversation_id.strip())
        if stable_conversation_id in taken:
            raise TranscriptIdentityError(
                f"conversation_id {stable_conversation_id} is already used on this opportunity."
            )

    return TranscriptIdentity(
        opportunity_id=stable_opportunity_id,
        transcript_id=stable_transcript_id,
        conversation_id=stable_conversation_id,
    )


def next_conversation_id(taken_conversation_ids: Sequence[str]) -> str:
    used: set[int] = set()
    for item in taken_conversation_ids:
        if not item or not item.strip():
            continue
        match = CONVERSATION_ID_RE.fullmatch(item.strip())
        if not match:
            raise TranscriptIdentityError(
                f"Invalid conversation_id '{item}'. Expected C1, C2, C3, …"
            )
        used.add(int(match.group(1)))
    next_number = max(used, default=0) + 1
    return f"C{next_number}"


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _require_uuid(value: str, *, field: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise TranscriptIdentityError(
            f"{field} must be a UUID. Do not invent a new id during regeneration."
        ) from exc
    return str(parsed)


def _require_conversation_id(value: str) -> str:
    if not CONVERSATION_ID_RE.fullmatch(value):
        raise TranscriptIdentityError(
            f"Invalid conversation_id '{value}'. Expected C1, C2, C3, …"
        )
    return value
