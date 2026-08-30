"""Wire BT-1 planner and Group A generators into AT-42 / AT-43 (Stage B)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from services.presentation.planner import (
    PresentationPlannerError,
    plan_presentation,
)
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
    GroupAContentGenerationError,
    StructuredGenerationRequest,
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PLAN_FIXTURE_PATH = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"
)
_GROUP_A_FIXTURE_DIR = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"
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
    try:
        plan = plan_presentation(framework_json, planner=FixturePlanningClient())
    except PresentationPlannerError:
        return json.loads(_PLAN_FIXTURE_PATH.read_text(encoding="utf-8"))
    return plan.model_dump(mode="json")


def build_slide_spec_for_planned_slide(
    *,
    planned: dict[str, Any],
    framework_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a SlideSpec: Group A via BT-9..13, other layouts stay metadata stubs (JJ/MS)."""
    order = int(planned["order"])
    layout_id = str(planned["layoutId"])
    source_chapter_ids = framework_refs_to_chapter_ids(planned.get("frameworkReferences") or [])
    if framework_json is None or layout_id not in _GROUP_A_LAYOUTS:
        return build_stub_slide_spec(
            order=order,
            layout_id=layout_id,
            source_chapter_ids=source_chapter_ids,
        )

    generate_fn, fixture_name = _GROUP_A_LAYOUTS[layout_id]
    try:
        result = generate_fn(
            copy.deepcopy(framework_json),
            structured_generate=_group_a_fixture_generator(layout_id),
            compress_fields=lambda offending, _violations: offending,
        )
        if result.status == "VALID" and isinstance(result.slide_spec, dict):
            spec = copy.deepcopy(result.slide_spec)
            spec["slideId"] = f"slide_{order:02d}"
            return spec
    except GroupAContentGenerationError:
        pass

    spec = json.loads((_GROUP_A_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    spec["slideId"] = f"slide_{order:02d}"
    return spec
