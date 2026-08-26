"""MS-7: COMPLIANCE_01 content generation from confirmed Framework chapter 8."""

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
    layout_id="COMPLIANCE_01",
    schema_filename="compliance_01.schema.json",
    allowed_chapter_ids=("8",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every items[i].icon and "
        "items[i].text; darkBackground when populated"
    ),
    instructions=(
        "Create COMPLIANCE_01 cards using only chapter 8 security, data-protection, "
        "and human-control commitments. Keep darkBackground true for the closing "
        "master. Never invent guardrails. Never output currency, investment, pricing, "
        "ROI, payback, costs, savings, or other monetary content. Do not invent "
        "metrics. AI must not set PowerPoint x, y, or width."
    ),
)


def generate_compliance_01(
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
