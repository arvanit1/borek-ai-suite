"""JJ-5: PROCESS_FLOW_01 generation from chapters 2 and 4."""

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
    layout_id="PROCESS_FLOW_01",
    schema_filename="process_flow_01.schema.json",
    allowed_chapter_ids=("2", "4"),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every "
        "phases[i].number, phases[i].name, and phases[i].description"
    ),
    instructions=(
        "Create a numbered to-be process from chapter 2 current-state steps and "
        "chapter 4 solution/to-be steps. Do not invent phases, systems, or controls "
        "absent from those chapters."
    ),
)


def generate_process_flow_01(
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
