"""Repair empty optional subtitle fields before SlideSpec validation."""

from __future__ import annotations

import copy
import re
from typing import Any

from services.validation.source_chapter_enforcement import (
    sync_root_source_chapter_ids_from_field_provenance,
)

SUBTITLE_MAX_LENGTH = 100
_SENTENCE_SPLIT = re.compile(r"[.;\n]+")


def repair_empty_subtitle(
    slide_spec: dict[str, Any],
    chapters: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Drop blank subtitles, or replace them with a source-grounded phrase when possible."""
    repaired = copy.deepcopy(slide_spec)
    subtitle = repaired.get("subtitle")
    if isinstance(subtitle, str) and subtitle.strip():
        return repaired

    repaired.pop("subtitle", None)
    _remove_provenance_path(repaired, "subtitle")

    grounded = _deterministic_grounded_subtitle(chapters)
    if grounded is not None:
        text, source_ids = grounded
        repaired["subtitle"] = text
        _set_provenance_path(repaired, "subtitle", source_ids)

    sync_root_source_chapter_ids_from_field_provenance(repaired)
    return repaired


def repair_ungrounded_numeric_headline(
    slide_spec: dict[str, Any],
    chapters: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Strip invented numbers from headline, or replace it with grounded chapter prose."""
    from services.slides.content_generation.group_a.common import _number_tokens

    repaired = copy.deepcopy(slide_spec)
    headline = repaired.get("headline")
    if not isinstance(headline, str):
        return repaired

    grounded_numbers = _number_tokens(chapters)
    invented = _number_tokens(headline) - grounded_numbers
    if not invented:
        return repaired

    stripped = headline
    for token in sorted(invented, key=len, reverse=True):
        stripped = re.sub(rf"(?<![\w]){re.escape(token)}%?(?![\w])", " ", stripped)
    stripped = re.sub(r"[ \t]{2,}", " ", stripped)
    stripped = re.sub(r"\s+([,.;:])", r"\1", stripped).strip()
    if stripped and not (_number_tokens(stripped) - grounded_numbers):
        repaired["headline"] = stripped
        return repaired

    fallback = _deterministic_grounded_headline(chapters)
    if fallback is not None:
        text, source_ids = fallback
        repaired["headline"] = text
        _set_provenance_path(repaired, "headline", source_ids)
        sync_root_source_chapter_ids_from_field_provenance(repaired)
    return repaired


def repair_executive_summary_slide_spec(
    slide_spec: dict[str, Any],
    chapters: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Keep EXECUTIVE_SUMMARY_01 subtitle and headline grounded before validation."""
    repaired = repair_empty_subtitle(slide_spec, chapters)
    return repair_ungrounded_numeric_headline(repaired, chapters)


def format_empty_subtitle_retry_message(message: str) -> str:
    if "subtitle" not in message:
        return message
    return (
        f"{message} The previous response returned an empty subtitle. "
        "subtitle must be a non-empty grounded string copied from the supplied "
        "chapter title or body, or omit subtitle entirely. Do not return an "
        "empty string."
    )


def is_empty_subtitle_validation_error(message: str) -> bool:
    return ".subtitle" in message and "non-empty" in message.casefold()


def _deterministic_grounded_subtitle(
    chapters: tuple[dict[str, Any], ...],
) -> tuple[str, tuple[str, ...]] | None:
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = chapter.get("chapter_id")
        if not isinstance(chapter_id, str):
            continue
        source_text = _chapter_source_text(chapter)
        if not source_text.strip():
            continue

        title = chapter.get("title")
        if isinstance(title, str):
            candidate = title.strip()
            if _fits_subtitle(candidate) and candidate.casefold() in source_text.casefold():
                return candidate, (chapter_id,)

        for sentence in _sentences(source_text):
            candidate = sentence.strip()
            if not _fits_subtitle(candidate):
                continue
            if candidate.casefold() in source_text.casefold():
                return candidate, (chapter_id,)
    return None


def _fits_subtitle(text: str) -> bool:
    return 1 <= len(text) <= SUBTITLE_MAX_LENGTH


HEADLINE_MAX_LENGTH = 180


def _deterministic_grounded_headline(
    chapters: tuple[dict[str, Any], ...],
) -> tuple[str, tuple[str, ...]] | None:
    from services.slides.content_generation.group_a.common import _number_tokens

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = chapter.get("chapter_id")
        if not isinstance(chapter_id, str):
            continue
        source_text = _chapter_source_text(chapter)
        if not source_text.strip():
            continue
        grounded_numbers = _number_tokens(chapter)
        for sentence in _sentences(source_text):
            candidate = sentence.strip()
            if not (1 <= len(candidate) <= HEADLINE_MAX_LENGTH):
                continue
            if _number_tokens(candidate) - grounded_numbers:
                continue
            if candidate.casefold() in source_text.casefold():
                return candidate, (chapter_id,)
    return None


def _sentences(text: str):
    for part in _SENTENCE_SPLIT.split(text):
        stripped = part.strip()
        if stripped:
            yield stripped


def _chapter_source_text(chapter: dict[str, Any]) -> str:
    parts: list[str] = []
    title = chapter.get("title")
    if isinstance(title, str) and title.strip():
        parts.append(title.strip())
    body_text = _chapter_body_text(chapter)
    if body_text.strip():
        parts.append(body_text.strip())
    return " ".join(parts)


def _chapter_body_text(chapter: dict[str, Any]) -> str:
    body = chapter.get("body")
    if isinstance(body, str):
        return body
    return " ".join(_iter_strings(body))


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)


def _remove_provenance_path(slide_spec: dict[str, Any], path: str) -> None:
    provenance = slide_spec.get("fieldProvenance")
    if not isinstance(provenance, list):
        return
    slide_spec["fieldProvenance"] = [
        entry
        for entry in provenance
        if not (isinstance(entry, dict) and entry.get("path") == path)
    ]


def _set_provenance_path(
    slide_spec: dict[str, Any],
    path: str,
    source_ids: tuple[str, ...],
) -> None:
    provenance = slide_spec.get("fieldProvenance")
    if not isinstance(provenance, list):
        provenance = []
    retained = [
        entry
        for entry in provenance
        if not (isinstance(entry, dict) and entry.get("path") == path)
    ]
    retained.append({"path": path, "sourceChapterIds": list(source_ids)})
    slide_spec["fieldProvenance"] = retained
