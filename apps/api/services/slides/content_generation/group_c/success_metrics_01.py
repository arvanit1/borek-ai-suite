"""MS-8: SUCCESS_METRICS_01 generation from confirmed chapters 3 and 9."""

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
    layout_id="SUCCESS_METRICS_01",
    schema_filename="success_metrics_01.schema.json",
    allowed_chapter_ids=("3", "9"),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every criteria[i].title "
        "and criteria[i].description"
    ),
    instructions=(
        "Create SUCCESS_METRICS_01 criteria using only chapters 3 and 9. Prefer "
        "non-monetary success measures from chapter 3. Chapter 9 may supply "
        "qualitative aims only after monetary values have been removed. Never "
        "output currency, investment, pricing, ROI, payback, costs, savings, or "
        "other monetary content. Do not invent metrics. AI must not set PowerPoint "
        "x, y, or width."
    ),
)


def generate_success_metrics_01(
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
