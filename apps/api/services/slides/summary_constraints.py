"""JJ-23: Load and register EXECUTIVE_SUMMARY_01 content constraints with AT-7."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from services.validation.constraint_validator import LayoutConstraintRegistry

ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "packages" / "contracts" / "constraints" / "summary.yaml"

SUMMARY_LAYOUT_IDS = ("EXECUTIVE_SUMMARY_01",)


def load_summary_constraint_configs() -> dict[str, dict[str, Any]]:
    """Load JSON-compatible YAML constraint data and validate its layout registry shape."""
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    layouts = document.get("layouts")
    if not isinstance(layouts, dict):
        raise RuntimeError("JJ-23 summary.yaml must define a layouts object")

    expected = set(SUMMARY_LAYOUT_IDS)
    actual = set(layouts)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise RuntimeError(
            f"JJ-23 summary layout ids mismatch: missing={missing}, unexpected={unexpected}"
        )

    configs: dict[str, dict[str, Any]] = {}
    for layout_id in SUMMARY_LAYOUT_IDS:
        config = layouts[layout_id]
        if not isinstance(config, dict) or not isinstance(config.get("properties"), dict):
            raise RuntimeError(f"JJ-23 {layout_id} config must define a properties object")
        configs[layout_id] = copy.deepcopy(config)
    return configs


def register_summary_constraints(
    registry: LayoutConstraintRegistry,
) -> LayoutConstraintRegistry:
    """Register JJ-23 EXECUTIVE_SUMMARY_01 constraints in an existing AT-7 registry."""
    for layout_id, config in load_summary_constraint_configs().items():
        registry.register(layout_id, config)
    return registry
