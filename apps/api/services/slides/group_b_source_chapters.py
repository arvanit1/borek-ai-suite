"""JJ-9: Group B chapter allowances for the shared BT-14 provenance validator."""

from __future__ import annotations

from typing import Any

from services.validation.source_chapter_enforcement import validate_field_provenance

GROUP_B_ALLOWED_CHAPTER_IDS: dict[str, tuple[str, ...]] = {
    "PROCESS_FLOW_01": ("2", "4"),
    "TIMELINE_01": ("10",),
    "MILESTONES_01": ("10",),
    "TEAM_FTE_01": ("10",),
}


def validate_group_b_field_provenance(slide_spec: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Enforce complete fieldProvenance for a Group B layout using shared AT-3 rules."""
    layout_id = slide_spec.get("layoutId")
    if layout_id not in GROUP_B_ALLOWED_CHAPTER_IDS:
        raise ValueError(f"Unsupported Group B layoutId: {layout_id!r}")
    allowed = GROUP_B_ALLOWED_CHAPTER_IDS[layout_id]
    return validate_field_provenance(
        slide_spec,
        real_chapter_ids=allowed,
        allowed_chapter_ids=allowed,
    )
