"""BT-9: COVER_01 content generation from confirmed Framework chapter 1."""

from __future__ import annotations

import copy
import re
from typing import Any

from services.slides.content_generation.group_a.common import (
    GroupAGenerationConfig,
    StructuredGenerator,
    _number_tokens,
    generate_group_a_slide_spec,
)
from services.slides.group_a_compression import GroupACompressFieldsFn
from services.validation.compression_retry import CompressionResult
from services.validation.source_chapter_enforcement import (
    SourceChapterEnforcementError,
    validate_field_provenance,
)

MAX_STAT_BADGES = 3
_STAT_BADGE_VALUE_MAX_LENGTH = 16
_STAT_BADGE_LABEL_MAX_LENGTH = 32
_STAT_BADGE_PATH = re.compile(r"^statBadges\[\d+\]")
_SOURCE_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{0,15}")
_SPELLED_NUMBER = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|percent)\b",
    re.IGNORECASE,
)


def repair_cover_ungrounded_stat_badges(
    slide_spec: dict[str, Any],
    chapters: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Drop COVER_01 stat badges whose numeric claims are absent from source chapters."""
    repaired = copy.deepcopy(slide_spec)
    chapter_ids = tuple(
        chapter["chapter_id"]
        for chapter in chapters
        if isinstance(chapter, dict) and isinstance(chapter.get("chapter_id"), str)
    )
    if not chapter_ids:
        return repaired

    try:
        provenance = validate_field_provenance(
            repaired,
            real_chapter_ids=chapter_ids,
            allowed_chapter_ids=chapter_ids,
        )
    except SourceChapterEnforcementError:
        provenance = {}

    badges = repaired.get("statBadges")
    if not isinstance(badges, list):
        return repaired

    chapters_by_id = {
        chapter["chapter_id"]: chapter
        for chapter in chapters
        if isinstance(chapter, dict) and isinstance(chapter.get("chapter_id"), str)
    }

    kept: list[tuple[dict[str, Any], tuple[str, ...]]] = []
    for index, badge in enumerate(badges):
        if not isinstance(badge, dict):
            continue
        value = badge.get("value")
        label = badge.get("label")
        if not isinstance(value, str) or not isinstance(label, str):
            continue

        value_path = f"statBadges[{index}].value"
        source_ids = provenance.get(value_path, chapter_ids)
        attributed = tuple(
            chapters_by_id[chapter_id]
            for chapter_id in source_ids
            if chapter_id in chapters_by_id
        )
        if not _stat_badge_value_is_grounded(value, attributed):
            continue
        kept.append((badge, source_ids))

    if len(kept) != len(badges):
        repaired["statBadges"] = [badge for badge, _sources in kept]
        _resync_cover_stat_badge_provenance(repaired, kept)

    if not repaired.get("statBadges"):
        fallback = _deterministic_grounded_non_numeric_badge(chapters, chapter_ids)
        if fallback is not None:
            badge, source_ids = fallback
            repaired["statBadges"] = [badge]
            _resync_cover_stat_badge_provenance(
                repaired,
                [(badge, source_ids)],
            )
    return repaired


def _deterministic_grounded_non_numeric_badge(
    chapters: tuple[dict[str, Any], ...],
    chapter_ids: tuple[str, ...],
) -> tuple[dict[str, Any], tuple[str, ...]] | None:
    chapters_by_id = {
        chapter["chapter_id"]: chapter
        for chapter in chapters
        if isinstance(chapter, dict) and isinstance(chapter.get("chapter_id"), str)
    }
    for chapter_id in chapter_ids:
        chapter = chapters_by_id.get(chapter_id)
        if chapter is None:
            continue
        source_text = _chapter_source_text(chapter)
        value = _select_grounded_non_numeric_value(source_text)
        if value is None:
            continue
        label = _select_grounded_non_numeric_label(source_text, value)
        if label is None:
            continue
        return ({"value": value, "label": label}, (chapter_id,))
    return None


def _select_grounded_non_numeric_value(source_text: str) -> str | None:
    if not source_text.strip():
        return None
    candidates: list[str] = []
    for match in _SOURCE_WORD.finditer(source_text):
        word = match.group(0)
        if len(word) > _STAT_BADGE_VALUE_MAX_LENGTH:
            continue
        if _number_tokens(word) or _looks_like_spelled_numeric_claim(word):
            continue
        normalized = word.casefold()
        if normalized not in {item.casefold() for item in candidates}:
            candidates.append(word)
    if not candidates:
        return None
    return max(candidates, key=len)


def _select_grounded_non_numeric_label(
    source_text: str,
    value: str,
) -> str | None:
    normalized_source = source_text.casefold()
    sentences = [
        segment.strip()
        for segment in re.split(r"[.;\n]+", source_text)
        if segment.strip()
    ]
    for sentence in sentences:
        if value.casefold() in sentence.casefold() and len(sentence) <= _STAT_BADGE_LABEL_MAX_LENGTH:
            return sentence
    title = source_text.strip()
    if value.casefold() in normalized_source and len(title) <= _STAT_BADGE_LABEL_MAX_LENGTH:
        return title
    if len(value) <= _STAT_BADGE_LABEL_MAX_LENGTH:
        return value
    return None


def _stat_badge_value_is_grounded(
    value: str,
    attributed: tuple[dict[str, Any], ...],
) -> bool:
    chapter_text = " ".join(_chapter_source_text(chapter) for chapter in attributed)
    normalized = value.casefold()
    if normalized and normalized in chapter_text.casefold():
        return True

    generated_numbers = _number_tokens(value)
    if generated_numbers:
        grounded_numbers = _number_tokens(attributed)
        return generated_numbers.issubset(grounded_numbers)

    if _looks_like_spelled_numeric_claim(value):
        return False
    return True


def _looks_like_spelled_numeric_claim(value: str) -> bool:
    return bool(_SPELLED_NUMBER.search(value))


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


def _resync_cover_stat_badge_provenance(
    slide_spec: dict[str, Any],
    kept: list[tuple[dict[str, Any], tuple[str, ...]]],
) -> None:
    provenance = slide_spec.get("fieldProvenance")
    if not isinstance(provenance, list):
        provenance = []
    retained = [
        entry
        for entry in provenance
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and not _STAT_BADGE_PATH.match(entry["path"])
    ]
    for index, (_badge, source_ids) in enumerate(kept):
        chapter_ids = list(source_ids)
        retained.append(
            {"path": f"statBadges[{index}].value", "sourceChapterIds": chapter_ids}
        )
        retained.append(
            {"path": f"statBadges[{index}].label", "sourceChapterIds": chapter_ids}
        )
    slide_spec["fieldProvenance"] = retained

    union: list[str] = []
    for entry in retained:
        for chapter_id in entry["sourceChapterIds"]:
            if chapter_id not in union:
                union.append(chapter_id)
    if union:
        slide_spec["sourceChapterIds"] = union


def _cover_retry_message(message: str) -> str:
    if "statBadges" not in message or "minimum" not in message.casefold():
        return message
    return (
        f"{message} Previous stat badges were removed because they were unsupported. "
        "Return at least one statBadge. Use a grounded numeric value only if it "
        "appears verbatim in the supplied chapter title or body. Otherwise use a "
        "short non-numeric value copied verbatim from the chapter title or body. "
        "Do not invent numbers or spell unsupported numbers as words."
    )


CONFIG = GroupAGenerationConfig(
    layout_id="COVER_01",
    schema_filename="cover_01.schema.json",
    allowed_chapter_ids=("1",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every "
        "statBadges[i].value and statBadges[i].label"
    ),
    instructions=(
        "Create COVER_01 content using only chapter 1. Include at least 1 and at "
        "most 3 statBadges. Prefer grounded quantitative facts only when the "
        "supplied chapter title or body contains the exact number. If the chapter "
        "contains no grounded numbers, include at least one short non-numeric "
        "statBadge whose value is copied verbatim from the chapter title or body. "
        "Select only grounded, non-commercial facts. Never output currency, "
        "investment, pricing, ROI, payback, costs, savings, or other monetary "
        "content. Do not invent metrics. Do not spell unsupported numbers as words."
    ),
    pre_validate_repair=repair_cover_ungrounded_stat_badges,
    format_retry_message=_cover_retry_message,
)


def generate_cover_01(
    framework_object: dict[str, Any],
    *,
    structured_generate: StructuredGenerator,
    compress_fields: GroupACompressFieldsFn,
) -> CompressionResult:
    return generate_group_a_slide_spec(
        framework_object,
        config=CONFIG,
        structured_generate=structured_generate,
        compress_fields=compress_fields,
    )
