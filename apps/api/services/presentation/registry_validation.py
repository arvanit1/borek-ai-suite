"""BT-2: runtime validation against the canonical Layout Registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from packages.contracts.validators import (
    ContractValidationError,
    layout_ids_from_registry,
)

LAYOUT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "contracts"
    / "layout_registry.json"
)


class UnregisteredLayoutError(ContractValidationError):
    """A PresentationPlan references a layout absent from the runtime registry."""


def registered_layout_ids() -> frozenset[str]:
    """Load allowed layout IDs from the canonical runtime registry."""
    registry = json.loads(LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8"))
    return frozenset(layout_ids_from_registry(registry))


def validate_registry_layout_selection(plan: Mapping[str, Any]) -> None:
    """Reject the complete plan when any slide uses an unregistered layoutId."""
    allowed = registered_layout_ids()
    slides = plan.get("slides")
    if not isinstance(slides, list):
        raise ContractValidationError("PresentationPlan.slides must be an array")

    for index, slide in enumerate(slides):
        layout_id = slide.get("layoutId") if isinstance(slide, dict) else None
        if layout_id not in allowed:
            raise UnregisteredLayoutError(
                f"Unregistered layoutId {layout_id!r} at slides[{index}]"
            )
