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
_STAT_BADGE_PATH = re.compile(r"^statBadges\[\d+\]")
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

    repaired["statBadges"] = [badge for badge, _sources in kept]
    if len(kept) != len(badges):
        _resync_cover_stat_badge_provenance(repaired, kept)
    return repaired


def _stat_badge_value_is_grounded(
    value: str,
    attributed: tuple[dict[str, Any], ...],
) -> bool:
    chapter_text = " ".join(_chapter_body_text(chapter) for chapter in attributed)
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


CONFIG = GroupAGenerationConfig(
    layout_id="COVER_01",
    schema_filename="cover_01.schema.json",
    allowed_chapter_ids=("1",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every "
        "statBadges[i].value and statBadges[i].label"
    ),
    instructions=(
        "Create COVER_01 content using only chapter 1. Include at most 3 "
        "statBadges — use only the strongest grounded quantitative facts. "
        "Select only grounded, non-commercial facts. Never output currency, "
        "investment, pricing, ROI, payback, costs, savings, or other monetary "
        "content. Do not invent metrics."
    ),
    pre_validate_repair=repair_cover_ungrounded_stat_badges,
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
