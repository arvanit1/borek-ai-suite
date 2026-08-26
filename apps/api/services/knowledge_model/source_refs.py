"""ES-6 — every knowledge entry must cite conversation_id + turn pointer."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from services.transcript.conversation_ids import CONVERSATION_ID_RE

KNOWLEDGE_BUCKETS = (
    "facts",
    "stated_requirements",
    "constraints",
    "named_systems",
    "named_rules",
    "named_exceptions",
    "people_and_roles",
    "timeline_mentions",
    "risks",
    "unknowns",
)

EXCERPT_POINTER_RE = re.compile(r"^turn:(\d+)$")


@dataclass(frozen=True)
class SourceRefViolation:
    path: str
    message: str


class SourceRefError(ValueError):
    """Missing or invalid source pointer. ``user_message`` is safe for the client."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def iter_knowledge_entries(model: dict[str, Any]) -> Iterable[tuple[str, int, dict[str, Any]]]:
    for bucket in KNOWLEDGE_BUCKETS:
        entries = model.get(bucket) or []
        if not isinstance(entries, list):
            raise SourceRefError(f"Knowledge bucket '{bucket}' must be a list.")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise SourceRefError(f"{bucket}[{index}] must be an object.")
            yield bucket, index, entry


def parse_turn_index(excerpt_pointer: str) -> int | None:
    match = EXCERPT_POINTER_RE.fullmatch((excerpt_pointer or "").strip())
    if not match:
        return None
    return int(match.group(1))


def source_id(ref: dict[str, Any]) -> str:
    return f"{ref.get('conversation_id', '')}:{ref.get('excerpt_pointer', '')}"


def validate_source_refs(
    model: dict[str, Any],
    *,
    allowed_conversation_ids: Sequence[str] | None = None,
    allowed_turn_indices: Sequence[int] | None = None,
) -> None:
    """Fail if any entry is missing a conversation_id + turn:<n> pointer."""
    violations = collect_knowledge_model_source_ref_violations(
        model,
        allowed_conversation_ids=allowed_conversation_ids,
        allowed_turn_indices=allowed_turn_indices,
    )
    if violations:
        raise SourceRefError(" ".join(item.message for item in violations))


def collect_knowledge_model_source_ref_violations(
    model: dict[str, Any],
    *,
    allowed_conversation_ids: Sequence[str] | None = None,
    allowed_turn_indices: Sequence[int] | None = None,
) -> list[SourceRefViolation]:
    """Return structured source_ref issues without raising (ES-31 retry)."""
    allowed_cids = (
        frozenset(item.strip() for item in allowed_conversation_ids if item and str(item).strip())
        if allowed_conversation_ids is not None
        else None
    )
    allowed_turns = frozenset(allowed_turn_indices) if allowed_turn_indices is not None else None

    violations: list[SourceRefViolation] = []
    for bucket, index, entry in iter_knowledge_entries(model):
        loc = f"{bucket}[{index}]"
        for message in _ref_list_issues(
            f"{loc}.source_refs",
            entry.get("source_refs"),
            allowed_conversation_ids=allowed_cids,
            allowed_turn_indices=allowed_turns,
        ):
            violations.append(SourceRefViolation(path=loc, message=message))
    return violations


def collect_customer_report_source_ref_violations(
    draft: dict[str, Any],
    *,
    allowed_conversation_ids: Sequence[str] | None = None,
    allowed_turn_indices: Sequence[int] | None = None,
) -> list[SourceRefViolation]:
    """Validate chapter-level source_refs on a customer-report draft (ES-31)."""
    allowed_cids = (
        frozenset(item.strip() for item in allowed_conversation_ids if item and str(item).strip())
        if allowed_conversation_ids is not None
        else None
    )
    allowed_turns = frozenset(allowed_turn_indices) if allowed_turn_indices is not None else None

    violations: list[SourceRefViolation] = []
    chapters = draft.get("chapters")
    if not isinstance(chapters, list):
        return [SourceRefViolation("chapters", "Customer report draft must include chapters.")]

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id") or "?")
        prefix = f'chapters[{chapter_id}].source_refs'
        for message in _ref_list_issues(
            prefix,
            chapter.get("source_refs"),
            allowed_conversation_ids=allowed_cids,
            allowed_turn_indices=allowed_turns,
        ):
            violations.append(SourceRefViolation(path=f"chapters[{chapter_id}]", message=message))
    return violations


def _ref_list_issues(
    prefix: str,
    refs: Any,
    *,
    allowed_conversation_ids: frozenset[str] | None,
    allowed_turn_indices: frozenset[int] | None,
) -> list[str]:
    if not isinstance(refs, list) or not refs:
        return [f"{prefix} is missing a conversation_id + turn pointer."]

    issues: list[str] = []
    for ref_index, ref in enumerate(refs):
        loc = f"{prefix}[{ref_index}]"
        if not isinstance(ref, dict):
            issues.append(f"{loc} must be an object with conversation_id and excerpt_pointer.")
            continue
        cid = str(ref.get("conversation_id") or "").strip()
        pointer = str(ref.get("excerpt_pointer") or "").strip()
        speaker = str(ref.get("speaker_role") or "").strip()
        if not cid:
            issues.append(f"{loc} is missing conversation_id.")
        elif not CONVERSATION_ID_RE.fullmatch(cid):
            issues.append(f"{loc} has invalid conversation_id '{cid}'. Expected C1, C2, C3, …")
        elif allowed_conversation_ids is not None and cid not in allowed_conversation_ids:
            issues.append(
                f"{loc} conversation_id '{cid}' does not match this transcript "
                f"({', '.join(sorted(allowed_conversation_ids))})."
            )
        if not pointer:
            issues.append(f"{loc} is missing a turn pointer (excerpt_pointer like turn:0).")
        else:
            turn_index = parse_turn_index(pointer)
            if turn_index is None:
                issues.append(
                    f"{loc} excerpt_pointer '{pointer}' is invalid. Use turn:<index> from the transcript."
                )
            elif allowed_turn_indices is not None and turn_index not in allowed_turn_indices:
                issues.append(
                    f"{loc} excerpt_pointer '{pointer}' does not match a turn in this transcript."
                )
        if not speaker:
            issues.append(f"{loc} is missing speaker_role.")
    return issues
