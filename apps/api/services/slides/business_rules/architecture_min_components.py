"""MS-13: ARCHITECTURE_01 must have at least two components.

This is a business rule, not only the MS-12 YAML `min_items` config. Call it
even when AT-7 is bypassed.
"""

from __future__ import annotations

from typing import Any

MIN_ARCHITECTURE_COMPONENTS = 2
ARCHITECTURE_LAYOUT_ID = "ARCHITECTURE_01"


class ArchitectureMinComponentsError(ValueError):
    """ARCHITECTURE_01 has fewer than two components."""


def validate_architecture_min_components(slide_spec: dict[str, Any]) -> None:
    """Fail if this is ARCHITECTURE_01 and `components` has fewer than two items.

    Other layout ids are ignored. The payload is never mutated.
    """
    if slide_spec.get("layoutId") != ARCHITECTURE_LAYOUT_ID:
        return

    components = slide_spec.get("components")
    count = len(components) if isinstance(components, list) else 0
    if count < MIN_ARCHITECTURE_COMPONENTS:
        raise ArchitectureMinComponentsError(
            f"{ARCHITECTURE_LAYOUT_ID} requires at least "
            f"{MIN_ARCHITECTURE_COMPONENTS} components, got {count}"
        )
