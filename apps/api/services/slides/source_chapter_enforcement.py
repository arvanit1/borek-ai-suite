"""JJ-9: Group B field-level provenance using the shared BT-14 validator."""

from services.slides.group_b_source_chapters import (
    GROUP_B_ALLOWED_CHAPTER_IDS,
    validate_group_b_field_provenance,
)

__all__ = [
    "GROUP_B_ALLOWED_CHAPTER_IDS",
    "validate_group_b_field_provenance",
]
