"""Stage B planning and slide-generation boundaries.

Group A remains BT-owned and fail-closed: the shared platform must inject live
LLM callbacks. Group B and Group C are routed to their owner generators. This
module contains no fixture or provider fallback; unavailable providers,
unowned layouts, and invalid generation results fail explicitly.
"""

from __future__ import annotations

import copy
from typing import Any

from services.presentation.planner import PlanningClient, plan_presentation
from services.slides.content_generation.group_a.common import StructuredGenerator
from services.slides.content_generation.group_a.context_01 import generate_context_01
from services.slides.content_generation.group_a.cover_01 import generate_cover_01
from services.slides.content_generation.group_a.problem_solution_01 import (
    generate_problem_solution_01,
)
from services.slides.content_generation.group_a.requirements_matrix_01 import (
    generate_requirements_matrix_01,
)
from services.slides.content_generation.group_a.scope_01 import generate_scope_01
from services.slides.content_generation.group_b import (
    generate_milestones_01,
    generate_process_flow_01,
    generate_team_fte_01,
    generate_timeline_01,
)
from services.slides.content_generation.group_c.architecture_01 import (
    generate_architecture_01,
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
from services.slides.group_a_compression import GroupACompressFieldsFn


class StageBIntegrationError(RuntimeError):
    """Base error for the production Stage B integration boundary."""


class StageBProviderUnavailableError(StageBIntegrationError):
    """The shared platform has not supplied a required live provider."""


class UnsupportedSlideGeneratorError(StageBIntegrationError):
    """No owner generator is registered for the requested layout."""


class SlideGenerationError(StageBIntegrationError):
    """A layout generator did not return a valid, persistable SlideSpec."""


class GroupASlideGenerationError(SlideGenerationError):
    """A Group A generator did not return a valid, persistable SlideSpec."""


_GROUP_A_LAYOUTS: dict[str, Any] = {
    "COVER_01": generate_cover_01,
    "CONTEXT_01": generate_context_01,
    "PROBLEM_SOLUTION_01": generate_problem_solution_01,
    "SCOPE_01": generate_scope_01,
    "REQUIREMENTS_MATRIX_01": generate_requirements_matrix_01,
}
_GROUP_B_LAYOUTS: dict[str, Any] = {
    "PROCESS_FLOW_01": generate_process_flow_01,
    "TIMELINE_01": generate_timeline_01,
    "MILESTONES_01": generate_milestones_01,
    "TEAM_FTE_01": generate_team_fte_01,
}
_GROUP_C_LAYOUTS: dict[str, Any] = {
    "ARCHITECTURE_01": generate_architecture_01,
    "COMPLIANCE_01": generate_compliance_01,
    "SUCCESS_METRICS_01": generate_success_metrics_01,
    "OPEN_QUESTIONS_01": generate_open_questions_01,
    "NEXT_STEPS_01": generate_next_steps_01,
}


def get_live_planning_client() -> PlanningClient:
    """Resolve the fixture or live BT-1 planner for the configured execution mode."""
    from app.services.stage_b_providers import get_runtime_planning_client

    return get_runtime_planning_client()


def get_live_structured_generator() -> StructuredGenerator:
    """Return the shared live structured-output callback once it is available."""
    raise StageBProviderUnavailableError(
        "No shared live structured-generation provider is registered for Stage B"
    )


def get_live_compression_fields() -> GroupACompressFieldsFn:
    """Return the shared targeted compression callback once it is available."""
    raise StageBProviderUnavailableError(
        "No shared live compression provider is registered for Stage B"
    )


def framework_refs_to_chapter_ids(refs: list[str]) -> list[str]:
    chapter_ids: list[str] = []
    for ref in refs:
        if ref.startswith("chapter_"):
            chapter_ids.append(ref.removeprefix("chapter_"))
        elif ref == "opportunity":
            chapter_ids.append("0")
    return chapter_ids or ["1"]


def plan_json_from_confirmed_framework(
    framework_json: dict[str, Any],
    *,
    planner: PlanningClient | None = None,
) -> dict[str, Any]:
    """Run BT-1 once and return only its validated PresentationPlan JSON."""
    live_planner = planner if planner is not None else get_live_planning_client()
    plan = plan_presentation(copy.deepcopy(framework_json), planner=live_planner)
    return plan.model_dump(mode="json")


def build_slide_spec_for_planned_slide(
    *,
    planned: dict[str, Any],
    framework_json: dict[str, Any] | None,
    structured_generate: StructuredGenerator | None = None,
    compress_fields: GroupACompressFieldsFn | None = None,
) -> dict[str, Any]:
    """Route one planned slide to its owner generator and return a validated SlideSpec.

    EXECUTIVE_SUMMARY_01 stays fail-closed until an owner supplies a generator.
    """
    order = int(planned["order"])
    layout_id = str(planned["layoutId"])
    generate_fn = (
        _GROUP_A_LAYOUTS.get(layout_id)
        or _GROUP_B_LAYOUTS.get(layout_id)
        or _GROUP_C_LAYOUTS.get(layout_id)
    )
    if generate_fn is None:
        raise UnsupportedSlideGeneratorError(
            f"UNSUPPORTED_SLIDE_GENERATOR: no owner generator for {layout_id!r}"
        )
    if framework_json is None:
        raise StageBIntegrationError(
            "A confirmed FrameworkObject is required for slide generation"
        )

    live_structured_generate = (
        structured_generate
        if structured_generate is not None
        else get_live_structured_generator()
    )
    live_compress_fields = (
        compress_fields if compress_fields is not None else get_live_compression_fields()
    )
    result = generate_fn(
        copy.deepcopy(framework_json),
        structured_generate=live_structured_generate,
        compress_fields=live_compress_fields,
    )
    error_cls = (
        GroupASlideGenerationError if layout_id in _GROUP_A_LAYOUTS else SlideGenerationError
    )
    if result.status != "VALID":
        raise error_cls(
            f"{layout_id} generation failed validation: "
            f"{result.message or result.error_code or 'VALIDATION_FAILED'}"
        )
    if not isinstance(result.slide_spec, dict):
        raise error_cls(f"{layout_id} generation returned VALID without a SlideSpec")

    slide_spec = copy.deepcopy(result.slide_spec)
    slide_spec["slideId"] = f"slide_{order:02d}"
    return slide_spec
