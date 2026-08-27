"""MS-6: ARCHITECTURE_01 content generation from confirmed chapters 6 and 7."""

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
    layout_id="ARCHITECTURE_01",
    schema_filename="architecture_01.schema.json",
    allowed_chapter_ids=("6", "7"),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every "
        "components[i].number, components[i].title, and components[i].description"
    ),
    instructions=(
        "Create ARCHITECTURE_01 numbered components using only chapters 6 and 7. "
        "Map systems, data-flow, and integration nodes from chapter 6 and client "
        "access or integration needs from chapter 7. Require at least two components. "
        "Never invent systems, connectors, or capabilities. Never output currency, "
        "investment, pricing, ROI, payback, costs, savings, or other monetary content. "
        "Do not invent metrics. AI must not set PowerPoint x, y, or width."
    ),
)


def generate_architecture_01(
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
