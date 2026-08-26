"""BT-11: PROBLEM_SOLUTION_01 generation from chapters 2 and 4."""

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
    layout_id="PROBLEM_SOLUTION_01",
    schema_filename="problem_solution_01.schema.json",
    allowed_chapter_ids=("2", "4"),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; problem.title and "
        "problem.description; solution.title and solution.description"
    ),
    instructions=(
        "Ground the problem in chapter 2 current-state content and the solution in "
        "chapter 4 to-be content. Do not infer a capability or commitment absent "
        "from chapter 4."
    ),
)


def generate_problem_solution_01(
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
