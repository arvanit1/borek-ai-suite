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
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every "
        "phases[i].id, phases[i].name, and phases[i].description; every "
        "milestones[i].id, milestones[i].name, and milestones[i].phaseId; "
        "milestones[i].date and milestones[i].description when populated"
    ),
    instructions=(
        "Create dual-band TIMELINE_01 content only from chapter 10. Keep milestone "
        "phaseId values aligned to phases[].id. Timeline end must not precede start. "
        "Do not invent dates, phases, or checkpoints. "
        "NUMBERS: Always spell out numbers as words when they appear in compound "
        "terms or as approximations. Write 'seventy percent', never '70%' unless the "
        "exact digit appears in the chapter text you were given. Write 'ten weeks', "
        "never '10 weeks' unless the digit 10 appears in your source chapters. "
        "Use digits only for quantities that appear as digits in the chapter text "
        "you were given."
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
