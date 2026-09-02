"""JJ-8: TEAM_FTE_01 generation from chapter 10 team composition content."""

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
    layout_id="TEAM_FTE_01",
    schema_filename="team_fte_01.schema.json",
    allowed_chapter_ids=("10",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; every "
        "roles[i].role, roles[i].fte, and roles[i].responsibility; every "
        "summary[i].label and summary[i].value"
    ),
    instructions=(
        "Create TEAM_FTE_01 role cards and summary stats only from chapter 10 team "
        "composition content. FTE values must stay non-negative. Do not invent roles, "
        "effort, or headcount."
    ),
)


def generate_team_fte_01(
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
