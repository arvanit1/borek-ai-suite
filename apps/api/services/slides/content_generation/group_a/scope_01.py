"""BT-12: SCOPE_01 content generation from chapters 3 and 5."""

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
    layout_id="SCOPE_01",
    schema_filename="scope_01.schema.json",
    allowed_chapter_ids=("3", "5"),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every included[i] and "
        "every later[i]"
    ),
    instructions=(
        "Populate included and later using only chapters 3 and 5. Every later item "
        "must be explicitly grounded in those chapters; never invent future scope."
    ),
)


def generate_scope_01(
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
