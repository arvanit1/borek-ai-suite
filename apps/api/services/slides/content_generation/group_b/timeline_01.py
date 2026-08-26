"""JJ-6: TIMELINE_01 generation from chapter 10."""

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
    layout_id="TIMELINE_01",
    schema_filename="timeline_01.schema.json",
    allowed_chapter_ids=("10",),
    instructions=(
        "Create dual-band TIMELINE_01 content only from chapter 10. Keep milestone "
        "phaseId values aligned to phases[].id. Timeline end must not precede start. "
        "Do not invent dates, phases, or checkpoints."
    ),
)


def generate_timeline_01(
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
