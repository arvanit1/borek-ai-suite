"""MS-10: NEXT_STEPS_01 content generation from confirmed Framework chapter 13."""

from __future__ import annotations

from typing import Any

from services.slides.content_generation.group_c.common import (
    GroupCGenerationConfig,
    StructuredGenerator,
    generate_group_c_slide_spec,
)
from services.slides.group_c_compression import GroupCCompressFieldsFn
from services.validation.compression_retry import CompressionResult

CONFIG = GroupCGenerationConfig(
    layout_id="NEXT_STEPS_01",
    schema_filename="next_steps_01.schema.json",
    allowed_chapter_ids=("13",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every checklist[i]; "
        "every steps[i].number and steps[i].text; darkBackground when populated"
    ),
    instructions=(
        "Create NEXT_STEPS_01 from chapter 13 only. Use checklist strings for "
        "already-done or remaining close-out items and numbered steps for what "
        "happens next. Keep darkBackground true for the closing master. Never "
        "invent owners, dates, or work. Never output currency, investment, "
        "pricing, ROI, payback, costs, savings, or other monetary content. Do not "
        "invent metrics. AI must not set PowerPoint x, y, or width."
    ),
)


def generate_next_steps_01(
    framework_object: dict[str, Any],
    *,
    structured_generate: StructuredGenerator,
    compress_fields: GroupCCompressFieldsFn,
) -> CompressionResult:
    return generate_group_c_slide_spec(
        framework_object,
        config=CONFIG,
        structured_generate=structured_generate,
        compress_fields=compress_fields,
    )
