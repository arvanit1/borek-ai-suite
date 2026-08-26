"""BT-9: COVER_01 content generation from confirmed Framework chapter 1."""

from __future__ import annotations

from typing import Any

from services.slides.content_generation.group_a.common import (
    GroupAGenerationConfig,
    StructuredGenerator,
    generate_group_a_slide_spec,
)
from services.slides.group_a_compression import GroupACompressFieldsFn
from services.validation.compression_retry import CompressionResult

CONFIG = GroupAGenerationConfig(
    layout_id="COVER_01",
    schema_filename="cover_01.schema.json",
    allowed_chapter_ids=("1",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every "
        "statBadges[i].value and statBadges[i].label"
    ),
    instructions=(
        "Create COVER_01 content using only chapter 1. Select only grounded, "
        "non-commercial facts. Never output currency, investment, pricing, ROI, "
        "payback, costs, savings, or other monetary content. Do not invent metrics."
    ),
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
