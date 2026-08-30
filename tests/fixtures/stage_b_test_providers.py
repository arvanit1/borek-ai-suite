"""Deterministic, test-only Stage B providers for API and integration suites."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
GROUP_A_FIXTURE_DIR = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"
)
GROUP_A_FIXTURES = {
    "COVER_01": "cover_01.realistic.json",
    "CONTEXT_01": "context_01.realistic.json",
    "PROBLEM_SOLUTION_01": "problem_solution_01.realistic.json",
    "SCOPE_01": "scope_01.realistic.json",
    "REQUIREMENTS_MATRIX_01": "requirements_matrix_01.realistic.json",
}
GROUP_B_FIXTURE_DIR = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"
)
GROUP_C_FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec"
LAYOUT_FIXTURES = {
    **{layout_id: GROUP_A_FIXTURE_DIR / filename for layout_id, filename in GROUP_A_FIXTURES.items()},
    "PROCESS_FLOW_01": GROUP_B_FIXTURE_DIR / "process_flow_01.realistic.json",
    "TIMELINE_01": GROUP_B_FIXTURE_DIR / "timeline_01.realistic.json",
    "MILESTONES_01": GROUP_B_FIXTURE_DIR / "milestones_01.realistic.json",
    "TEAM_FTE_01": GROUP_B_FIXTURE_DIR / "team_fte_01.realistic.json",
    "ARCHITECTURE_01": GROUP_C_FIXTURE_DIR / "architecture_01.minimal.json",
    "COMPLIANCE_01": GROUP_C_FIXTURE_DIR / "compliance_01.minimal.json",
    "SUCCESS_METRICS_01": GROUP_C_FIXTURE_DIR / "success_metrics_01.minimal.json",
    "OPEN_QUESTIONS_01": GROUP_C_FIXTURE_DIR / "open_questions_01.minimal.json",
    "NEXT_STEPS_01": GROUP_C_FIXTURE_DIR / "next_steps_01.minimal.json",
}
GROUP_A_PLAN = {
    "schema_version": "1.0",
    "title": "Deterministic Group A test presentation",
    "slides": [
        {
            "order": 1,
            "purpose": "cover",
            "layoutId": "COVER_01",
            "frameworkReferences": ["chapter_1"],
        },
        {
            "order": 2,
            "purpose": "context",
            "layoutId": "CONTEXT_01",
            "frameworkReferences": ["chapter_1", "chapter_2"],
        },
        {
            "order": 3,
            "purpose": "problem and solution",
            "layoutId": "PROBLEM_SOLUTION_01",
            "frameworkReferences": ["chapter_2", "chapter_4"],
        },
        {
            "order": 4,
            "purpose": "scope",
            "layoutId": "SCOPE_01",
            "frameworkReferences": ["chapter_3", "chapter_5"],
        },
        {
            "order": 5,
            "purpose": "requirements",
            "layoutId": "REQUIREMENTS_MATRIX_01",
            "frameworkReferences": ["chapter_5"],
        },
    ],
}


class DeterministicPlanningClient:
    def complete_planning(self, **_kwargs: Any) -> dict[str, Any]:
        return copy.deepcopy(GROUP_A_PLAN)


def deterministic_structured_generate(request: Any) -> dict[str, Any]:
    path = LAYOUT_FIXTURES[request.layout_id]
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_compress_fields(
    offending: dict[str, str],
    violations: list[Any],
) -> dict[str, str]:
    limits = {violation.path: violation.limit for violation in violations}
    return {
        path: value[: limits[path]] if isinstance(limits.get(path), int) else value
        for path, value in offending.items()
    }


def install_stage_b_test_providers(monkeypatch: Any) -> None:
    """Install deterministic providers without changing the production defaults."""
    from app.services import stage_b_orchestration

    monkeypatch.setattr(
        stage_b_orchestration,
        "get_live_planning_client",
        lambda: DeterministicPlanningClient(),
    )
    monkeypatch.setattr(
        stage_b_orchestration,
        "get_live_structured_generator",
        lambda: deterministic_structured_generate,
    )
    monkeypatch.setattr(
        stage_b_orchestration,
        "get_live_compression_fields",
        lambda: deterministic_compress_fields,
    )
