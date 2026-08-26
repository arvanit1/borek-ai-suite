"""MS-9: OPEN_QUESTIONS_01 content generation from confirmed Framework chapter 11."""

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
    layout_id="OPEN_QUESTIONS_01",
    schema_filename="open_questions_01.schema.json",
    allowed_chapter_ids=("11",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; left.heading and every "
        "left.items[i]; right.heading and every right.items[i]"
    ),
    instructions=(
        "Create OPEN_QUESTIONS_01 as two columns from chapter 11 only. Put open "
        "questions or dependencies on the left and assumptions on the right. Never "
        "invent questions, owners, or consequences. Never output currency, "
        "investment, pricing, ROI, payback, costs, savings, or other monetary "
        "content. Do not invent metrics. AI must not set PowerPoint x, y, or width."
    ),
)


def generate_open_questions_01(
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
