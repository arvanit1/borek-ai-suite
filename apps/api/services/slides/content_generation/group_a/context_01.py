"""BT-10: CONTEXT_01 content generation from confirmed chapters 1 and 2."""

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
    layout_id="CONTEXT_01",
    schema_filename="context_01.schema.json",
    allowed_chapter_ids=("1", "2"),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; problem.title and "
        "problem.description; solution.title and solution.description; "
        "currentState.title and currentState.description; targetState.title and "
        "targetState.description"
    ),
    instructions=(
        "Create the problem, solution, currentState, and targetState blocks using "
        "only chapters 1 and 2. Select, shorten, reorganize, or paraphrase grounded "
        "content only; do not add facts or capabilities. "
        "NUMBERS: Always spell out numbers as words when they appear in compound "
        "terms or process names. Write 'three-way match', never '3-way match'. "
        "Write 'three steps', never '3 steps'. Write 'two systems', never '2 systems'. "
        "Use digits only for quantities that appear as digits in the chapter text "
        "you were given."
    ),
)


def generate_context_01(
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
