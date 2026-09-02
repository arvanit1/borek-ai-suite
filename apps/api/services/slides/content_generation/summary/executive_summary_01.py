"""JJ-23: EXECUTIVE_SUMMARY_01 content generation from confirmed Framework chapter 1."""

from __future__ import annotations

from typing import Any

from services.slides.content_generation.group_a.common import (
    GROUP_A_SCHEMA_DIR,
    GroupAGenerationConfig,
    StructuredGenerator,
    generate_group_a_slide_spec,
)
from services.slides.group_a_compression import GroupACompressFieldsFn
from services.slides.summary_compression import validate_and_compress_summary_slide_spec
from services.validation.compression_retry import CompressionResult

SUMMARY_SCHEMA_DIR = GROUP_A_SCHEMA_DIR.parent / "summary"

CONFIG = GroupAGenerationConfig(
    layout_id="EXECUTIVE_SUMMARY_01",
    schema_filename="executive_summary_01.schema.json",
    allowed_chapter_ids=("1",),
    provenance_path_guidance=(
        "title; subtitle and sectionLabel when populated; headline; every "
        "highlights[i].title and highlights[i].description"
    ),
    instructions=(
        "Create EXECUTIVE_SUMMARY_01 content using only chapter 1. Write one "
        "grounded headline and three or four highlight cards. Select, shorten, "
        "reorganize, or paraphrase grounded content only; do not add facts. "
        "Never output currency, investment, pricing, ROI, payback, costs, "
        "savings, or other monetary content. Do not invent metrics. "
        "NUMBERS: Always spell out numbers as words when they appear in compound "
        "terms. Write 'three-way match', never '3-way match'. Use digits only "
        "for quantities that appear as digits in the chapter text you were given."
    ),
    schema_dir=SUMMARY_SCHEMA_DIR,
)


def generate_executive_summary_01(
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
        validate_and_compress=validate_and_compress_summary_slide_spec,
    )
