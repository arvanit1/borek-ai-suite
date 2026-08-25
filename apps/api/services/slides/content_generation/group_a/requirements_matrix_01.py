"""BT-13: REQUIREMENTS_MATRIX_01 generation from confirmed chapter 5."""

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
    layout_id="REQUIREMENTS_MATRIX_01",
    schema_filename="requirements_matrix_01.schema.json",
    allowed_chapter_ids=("5",),
    instructions=(
        "Create requirement items only from chapter 5 rules and requirements. Use "
        "only semantic statuses included, partial, or later. Never output colors, "
        "style tokens, or other presentation controls."
    ),
)


def generate_requirements_matrix_01(
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
