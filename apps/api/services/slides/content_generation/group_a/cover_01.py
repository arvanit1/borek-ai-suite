"""BT-9: COVER_01 content generation from confirmed Framework chapter 1."""

from __future__ import annotations

import copy
import re
from typing import Any

from services.slides.content_generation.group_a.common import (
    GroupAGenerationConfig,
    StructuredGenerator,
    generate_group_a_slide_spec,
)
from services.slides.group_a_compression import GroupACompressFieldsFn
from services.validation.compression_retry import CompressionResult

MAX_STAT_BADGES = 3
_TRIMMED_BADGE_PATH = re.compile(r"^statBadges\[(\d+)\]")

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
)


def trim_overflow_stat_badges(slide_spec: dict[str, Any]) -> dict[str, Any]:
    """Keep the first 3 already-generated badges and drop stale provenance.

    Live models can emit more than three ``statBadges`` even though BT-15 caps
    the array at 3. This is a COVER_01-only cardinality repair: it does not
    invent badge content, rewrite values, or rank badges. Extra items are
    dropped in emission order so the existing BT-16 text-compression loop can
    still fail-close on other layouts and on non-cardinality violations.
    """
    badges = slide_spec.get("statBadges")
    if not isinstance(badges, list) or len(badges) <= MAX_STAT_BADGES:
        return slide_spec

    repaired = copy.deepcopy(slide_spec)
    repaired["statBadges"] = copy.deepcopy(badges[:MAX_STAT_BADGES])
    provenance = repaired.get("fieldProvenance")
    if not isinstance(provenance, list):
        return repaired

    kept_entries: list[Any] = []
    union: list[str] = []
    for entry in provenance:
        if isinstance(entry, dict) and _is_trimmed_badge_path(entry.get("path")):
            continue
        kept_entries.append(entry)
        if isinstance(entry, dict):
            for chapter_id in entry.get("sourceChapterIds") or []:
                if isinstance(chapter_id, str) and chapter_id not in union:
                    union.append(chapter_id)
    repaired["fieldProvenance"] = kept_entries
    if union:
        repaired["sourceChapterIds"] = union
    return repaired


def _is_trimmed_badge_path(path: Any) -> bool:
    if not isinstance(path, str):
        return False
    match = _TRIMMED_BADGE_PATH.match(path)
    return match is not None and int(match.group(1)) >= MAX_STAT_BADGES


def generate_cover_01(
    framework_object: dict[str, Any],
    *,
    structured_generate: StructuredGenerator,
    compress_fields: GroupACompressFieldsFn,
) -> CompressionResult:
    def generate_and_trim(request: Any) -> dict[str, Any]:
        generated = structured_generate(request)
        if not isinstance(generated, dict):
            return generated
        return trim_overflow_stat_badges(generated)

    return generate_group_a_slide_spec(
        framework_object,
        config=CONFIG,
        structured_generate=generate_and_trim,
        compress_fields=compress_fields,
    )
