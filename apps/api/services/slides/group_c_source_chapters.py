"""MS-11: Group C chapter allowances for the shared BT-14 provenance validator."""

from __future__ import annotations

from typing import Any

from services.validation.source_chapter_enforcement import validate_field_provenance

GROUP_C_ALLOWED_CHAPTER_IDS: dict[str, tuple[str, ...]] = {
    "ARCHITECTURE_01": ("6", "7"),
    "COMPLIANCE_01": ("8",),
    "SUCCESS_METRICS_01": ("3", "9"),
    "OPEN_QUESTIONS_01": ("11",),
    "NEXT_STEPS_01": ("13",),
}


def validate_group_c_field_provenance(slide_spec: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Enforce complete fieldProvenance for a Group C layout using shared AT-3 rules."""
    layout_id = slide_spec.get("layoutId")
    if layout_id not in GROUP_C_ALLOWED_CHAPTER_IDS:
        raise ValueError(f"Unsupported Group C layoutId: {layout_id!r}")
    allowed = GROUP_C_ALLOWED_CHAPTER_IDS[layout_id]
    return validate_field_provenance(
        slide_spec,
        real_chapter_ids=allowed,
        allowed_chapter_ids=allowed,
    )
