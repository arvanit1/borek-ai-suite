"""MS-12: Load and register Group C layout content constraints with AT-7."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from services.validation.constraint_validator import LayoutConstraintRegistry

ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "packages" / "contracts" / "constraints" / "group_c.yaml"

GROUP_C_LAYOUT_IDS = (
    "ARCHITECTURE_01",
    "COMPLIANCE_01",
    "SUCCESS_METRICS_01",
    "OPEN_QUESTIONS_01",
    "NEXT_STEPS_01",
)


def load_group_c_constraint_configs() -> dict[str, dict[str, Any]]:
    """Load JSON-compatible YAML constraint data and validate its layout registry shape."""
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    layouts = document.get("layouts")
    if not isinstance(layouts, dict):
        raise RuntimeError("MS-12 group_c.yaml must define a layouts object")

    expected = set(GROUP_C_LAYOUT_IDS)
    actual = set(layouts)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise RuntimeError(
            f"MS-12 Group C layout ids mismatch: missing={missing}, unexpected={unexpected}"
        )

    configs: dict[str, dict[str, Any]] = {}
    for layout_id in GROUP_C_LAYOUT_IDS:
        config = layouts[layout_id]
        if not isinstance(config, dict) or not isinstance(config.get("properties"), dict):
            raise RuntimeError(f"MS-12 {layout_id} config must define a properties object")
        configs[layout_id] = copy.deepcopy(config)
    return configs


def register_group_c_constraints(
    registry: LayoutConstraintRegistry,
) -> LayoutConstraintRegistry:
    """Register all five MS-12 configs in an existing AT-7 registry."""
    for layout_id, config in load_group_c_constraint_configs().items():
        registry.register(layout_id, config)
    return registry
