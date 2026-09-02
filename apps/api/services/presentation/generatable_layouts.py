"""Layouts that have an owner generator and a renderer.

GENERATABLE_LAYOUT_IDS is the owner-complete layout set. Unknown layout ids
are still skipped so a corrupted saved plan cannot fail the whole deck.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

PRESENTATION_PLAN_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "contracts"
    / "presentation_plan.schema.json"
)

GENERATABLE_LAYOUT_IDS = frozenset(
    {
        "COVER_01",
        "CONTEXT_01",
        "PROBLEM_SOLUTION_01",
        "SCOPE_01",
        "REQUIREMENTS_MATRIX_01",
        "EXECUTIVE_SUMMARY_01",
        "PROCESS_FLOW_01",
        "TIMELINE_01",
        "MILESTONES_01",
        "TEAM_FTE_01",
        "ARCHITECTURE_01",
        "COMPLIANCE_01",
        "SUCCESS_METRICS_01",
        "OPEN_QUESTIONS_01",
        "NEXT_STEPS_01",
    }
)


def planning_target_schema() -> dict[str, Any]:
    """Canonical PresentationPlan schema with only generatable layoutId values."""
    schema = json.loads(PRESENTATION_PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
    layout_def = (schema.get("$defs") or {}).get("LayoutId")
    if isinstance(layout_def, dict) and isinstance(layout_def.get("enum"), list):
        layout_def["enum"] = [
            layout_id
            for layout_id in layout_def["enum"]
            if layout_id in GENERATABLE_LAYOUT_IDS
        ]
    return schema


def filter_generatable_planned_slides(
    plan_json: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Split a saved plan into generatable slides vs skipped layout ids."""
    kept: list[dict[str, Any]] = []
    skipped: list[str] = []
    for planned in sorted(plan_json.get("slides") or [], key=lambda item: item["order"]):
        copy_planned = copy.deepcopy(planned)
        layout_id = str(copy_planned.get("layoutId") or "")
        if layout_id in GENERATABLE_LAYOUT_IDS:
            kept.append(copy_planned)
        elif layout_id:
            skipped.append(layout_id)
    return kept, skipped


def as_approved_generatable_plan(plan_json: dict[str, Any]) -> dict[str, Any]:
    """Return the plan that AT-10 may treat as approved: owned layouts, orders 1..n."""
    kept, skipped = filter_generatable_planned_slides(plan_json)
    if not kept:
        raise ValueError(
            "Approved plan must contain at least one generatable slide; "
            f"unimplemented layouts were {skipped}"
        )
    approved = copy.deepcopy(plan_json)
    approved["slides"] = []
    for index, slide in enumerate(kept, start=1):
        item = copy.deepcopy(slide)
        item["order"] = index
        approved["slides"].append(item)
    return approved
