"""JJ-9: sourceChapterIds must cite real FrameworkObject chapters."""

from __future__ import annotations

from typing import Any, Collection

VALID_CHAPTER_IDS = frozenset(str(index) for index in range(14))


class SourceChapterValidationError(ValueError):
    """Generated provenance does not match allowed Framework chapters."""


def validate_source_chapter_ids(
    slide_spec: dict[str, Any],
    *,
    allowed_chapter_ids: Collection[str],
    layout_id: str,
) -> None:
    """Reject empty, duplicate, invented, or out-of-layout source chapter ids."""
    allowed = tuple(allowed_chapter_ids)
    source_chapter_ids = slide_spec.get("sourceChapterIds")
    if (
        not isinstance(source_chapter_ids, list)
        or not source_chapter_ids
        or any(not isinstance(item, str) for item in source_chapter_ids)
        or len(set(source_chapter_ids)) != len(source_chapter_ids)
        or not set(source_chapter_ids).issubset(VALID_CHAPTER_IDS)
        or not set(source_chapter_ids).issubset(allowed)
    ):
        raise SourceChapterValidationError(
            f"{layout_id}.sourceChapterIds must be a non-empty, duplicate-free "
            f"subset of allowed chapters {list(allowed)}"
        )
