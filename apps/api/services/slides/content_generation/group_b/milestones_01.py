"""JJ-7: MILESTONES_01 generation from chapter 10."""

from __future__ import annotations

from typing import Any

from services.slides.content_generation.group_b.common import (
    GroupBGenerationConfig,
    StructuredGenerator,
    generate_group_b_slide_spec,
)
from services.slides.group_b_compression import GroupBCompressFieldsFn
from services.validation.compression_retry import CompressionResult

CONFIG = GroupBGenerationConfig(
    layout_id="MILESTONES_01",
    schema_filename="milestones_01.schema.json",
    allowed_chapter_ids=("10",),
    instructions=(
        "Create a standalone milestone list from chapter 10 delivery checkpoints. "
        "Do not attach phaseId. Do not invent dates or duplicate milestone identities."
    ),
)


def generate_milestones_01(
    framework_object: dict[str, Any],
    *,
    structured_generate: StructuredGenerator,
    compress_fields: GroupBCompressFieldsFn,
) -> CompressionResult:
    return generate_group_b_slide_spec(
        framework_object,
        config=CONFIG,
        structured_generate=structured_generate,
        compress_fields=compress_fields,
    )
