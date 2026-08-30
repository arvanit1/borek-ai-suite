"""Wire the Stage B planner and layout generators into AT-42 / AT-43."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from services.presentation.planner import plan_presentation
from services.slides.content_generation.group_a.context_01 import generate_context_01
from services.slides.content_generation.group_a.cover_01 import generate_cover_01
from services.slides.content_generation.group_a.problem_solution_01 import (
    generate_problem_solution_01,
)
from services.slides.content_generation.group_a.requirements_matrix_01 import (
    generate_requirements_matrix_01,
)
from services.slides.content_generation.group_a.scope_01 import generate_scope_01
from services.slides.content_generation.group_a.common import (
    StructuredGenerationRequest,
)
from services.slides.content_generation.group_b import (
    generate_milestones_01,
    generate_process_flow_01,
    generate_team_fte_01,
    generate_timeline_01,
)
from services.slides.content_generation.group_b.common import (
    StructuredGenerationRequest as GroupBStructuredGenerationRequest,
)
from services.slides.content_generation.group_c.architecture_01 import (
    generate_architecture_01,
)
from services.slides.content_generation.group_c.common import (
    StructuredGenerationRequest as GroupCStructuredGenerationRequest,
)
from services.slides.content_generation.group_c.compliance_01 import (
    generate_compliance_01,
)
from services.slides.content_generation.group_c.next_steps_01 import (
    generate_next_steps_01,
)
from services.slides.content_generation.group_c.open_questions_01 import (
    generate_open_questions_01,
)
from services.slides.content_generation.group_c.success_metrics_01 import (
    generate_success_metrics_01,
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PLAN_FIXTURE_PATH = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"
)
_GROUP_A_FIXTURE_DIR = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"
)
_GROUP_B_FIXTURE_DIR = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"
)
_GROUP_C_FIXTURE_DIR = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "slide_spec"
)

_GROUP_A_LAYOUTS: dict[str, Any] = {
    "COVER_01": (generate_cover_01, "cover_01.realistic.json"),
    "CONTEXT_01": (generate_context_01, "context_01.realistic.json"),
    "PROBLEM_SOLUTION_01": (generate_problem_solution_01, "problem_solution_01.realistic.json"),
    "SCOPE_01": (generate_scope_01, "scope_01.realistic.json"),
    "REQUIREMENTS_MATRIX_01": (
        generate_requirements_matrix_01,
        "requirements_matrix_01.realistic.json",
    ),
}
_GROUP_B_LAYOUTS: dict[str, Any] = {
    "PROCESS_FLOW_01": (generate_process_flow_01, "process_flow_01.realistic.json"),
    "TIMELINE_01": (generate_timeline_01, "timeline_01.realistic.json"),
    "MILESTONES_01": (generate_milestones_01, "milestones_01.realistic.json"),
    "TEAM_FTE_01": (generate_team_fte_01, "team_fte_01.realistic.json"),
}
_GROUP_C_LAYOUTS: dict[str, Any] = {
    "ARCHITECTURE_01": (generate_architecture_01, "architecture_01.minimal.json"),
    "COMPLIANCE_01": (generate_compliance_01, "compliance_01.minimal.json"),
    "SUCCESS_METRICS_01": (
        generate_success_metrics_01,
        "success_metrics_01.minimal.json",
    ),
    "OPEN_QUESTIONS_01": (
        generate_open_questions_01,
        "open_questions_01.minimal.json",
    ),
    "NEXT_STEPS_01": (generate_next_steps_01, "next_steps_01.minimal.json"),
}


class StageBOrchestrationError(RuntimeError):
    """A Stage B owner implementation did not produce a valid persisted artifact."""


class FixturePlanningClient:
    """BT-1 PlanningClient that returns the canonical plan fixture (no live OpenAI)."""

    def complete_planning(
        self,
        *,
        planning_input: dict[str, Any] | None = None,
        prompt_version: str = "v1",
        retry_count: int = 0,
    ) -> dict[str, Any]:
        _ = (planning_input, prompt_version, retry_count)
        return json.loads(_PLAN_FIXTURE_PATH.read_text(encoding="utf-8"))


def _group_a_fixture_generator(layout_id: str) -> Any:
    filename = _GROUP_A_LAYOUTS[layout_id][1]

    def generate(request: StructuredGenerationRequest) -> dict[str, Any]:
        _ = request
        return json.loads((_GROUP_A_FIXTURE_DIR / filename).read_text(encoding="utf-8"))

    return generate


def _group_b_fixture_generator(layout_id: str) -> Any:
    filename = _GROUP_B_LAYOUTS[layout_id][1]

    def generate(request: GroupBStructuredGenerationRequest) -> dict[str, Any]:
        _ = request
        return json.loads((_GROUP_B_FIXTURE_DIR / filename).read_text(encoding="utf-8"))

    return generate


def _group_c_fixture_generator(layout_id: str) -> Any:
    filename = _GROUP_C_LAYOUTS[layout_id][1]

    def generate(request: GroupCStructuredGenerationRequest) -> dict[str, Any]:
        _ = request
        return json.loads((_GROUP_C_FIXTURE_DIR / filename).read_text(encoding="utf-8"))

    return generate


def framework_refs_to_chapter_ids(refs: list[str]) -> list[str]:
    chapter_ids: list[str] = []
    for ref in refs:
        if ref.startswith("chapter_"):
            chapter_ids.append(ref.removeprefix("chapter_"))
        elif ref == "opportunity":
            chapter_ids.append("0")
    return chapter_ids or ["1"]


def build_stub_slide_spec(
    *,
    order: int,
    layout_id: str,
    source_chapter_ids: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "slideId": f"slide_{order:02d}",
        "layoutId": layout_id,
        "title": f"Slide {order}",
        "sourceChapterIds": source_chapter_ids,
    }


def plan_json_from_confirmed_framework(framework_json: dict[str, Any]) -> dict[str, Any]:
    """Run BT-1 `plan_presentation` and return JSON for persistence."""
    plan = plan_presentation(framework_json, planner=FixturePlanningClient())
    return plan.model_dump(mode="json")


def build_slide_spec_for_planned_slide(
    *,
    planned: dict[str, Any],
    framework_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a validated SlideSpec through the owner-provided layout generator."""
    order = int(planned["order"])
    layout_id = str(planned["layoutId"])
    source_chapter_ids = framework_refs_to_chapter_ids(planned.get("frameworkReferences") or [])
    if framework_json is None:
        return build_stub_slide_spec(
            order=order,
            layout_id=layout_id,
            source_chapter_ids=source_chapter_ids,
        )

    if layout_id in _GROUP_A_LAYOUTS:
        generate_fn, _fixture_name = _GROUP_A_LAYOUTS[layout_id]
        structured_generate = _group_a_fixture_generator(layout_id)
    elif layout_id in _GROUP_B_LAYOUTS:
        generate_fn, _fixture_name = _GROUP_B_LAYOUTS[layout_id]
        structured_generate = _group_b_fixture_generator(layout_id)
    elif layout_id in _GROUP_C_LAYOUTS:
        generate_fn, _fixture_name = _GROUP_C_LAYOUTS[layout_id]
        structured_generate = _group_c_fixture_generator(layout_id)
    else:
        return build_stub_slide_spec(
            order=order,
            layout_id=layout_id,
            source_chapter_ids=source_chapter_ids,
        )

    result = generate_fn(
        copy.deepcopy(framework_json),
        structured_generate=structured_generate,
        compress_fields=lambda offending, _violations: offending,
    )
    if result.status != "VALID" or not isinstance(result.slide_spec, dict):
        raise StageBOrchestrationError(
            f"{layout_id} generation did not produce a valid SlideSpec"
        )

    spec = copy.deepcopy(result.slide_spec)
    spec["slideId"] = f"slide_{order:02d}"
    return spec
