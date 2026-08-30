"""BT-owned Stage B planning and Group A content-generation boundaries.

The shared platform must provide the live LLM callbacks. This module deliberately
contains no fixture or provider fallback: unavailable providers, unsupported layouts,
and invalid generation results fail explicitly.
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
from services.slides.group_a_compression import GroupACompressFieldsFn


class StageBIntegrationError(RuntimeError):
    """Base error for the production Stage B integration boundary."""


class StageBProviderUnavailableError(StageBIntegrationError):
    """The shared platform has not supplied a required live provider."""


class UnsupportedSlideGeneratorError(StageBIntegrationError):
    """The BT-owned router was asked to generate a non-Group-A layout."""


class GroupASlideGenerationError(StageBIntegrationError):
    """A Group A generator did not return a valid, persistable SlideSpec."""


_GROUP_A_LAYOUTS: dict[str, Any] = {
    "COVER_01": generate_cover_01,
    "CONTEXT_01": generate_context_01,
    "PROBLEM_SOLUTION_01": generate_problem_solution_01,
    "SCOPE_01": generate_scope_01,
    "REQUIREMENTS_MATRIX_01": generate_requirements_matrix_01,
}


def get_live_planning_client() -> PlanningClient:
    """Return the shared live planner once AT provides its production implementation."""
    raise StageBProviderUnavailableError(
        "No shared live PlanningClient is registered for Stage B"
    )


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
    """Route one planned Group A slide and return its validated SlideSpec.

    Group B, Group C, and EXECUTIVE_SUMMARY_01 are deliberately outside this
    BT-owned router. The future shared dispatcher must route those layouts to their
    respective owners rather than representing them as successful metadata stubs.
    """
    order = int(planned["order"])
    layout_id = str(planned["layoutId"])
    generate_fn = _GROUP_A_LAYOUTS.get(layout_id)
    if generate_fn is None:
        raise UnsupportedSlideGeneratorError(
            f"UNSUPPORTED_SLIDE_GENERATOR: no BT Group A generator for {layout_id!r}"
        )
    if framework_json is None:
        raise StageBIntegrationError(
            "A confirmed FrameworkObject is required for Group A generation"
        )

    live_structured_generate = (
        structured_generate
        if structured_generate is not None
        else get_live_structured_generator()
    )
    live_compress_fields = (
        compress_fields
        if compress_fields is not None
        else get_live_compression_fields()
    )
    result = generate_fn(
        copy.deepcopy(framework_json),
        structured_generate=live_structured_generate,
        compress_fields=live_compress_fields,
    )
    if result.status != "VALID":
        raise GroupASlideGenerationError(
            f"{layout_id} generation failed validation: "
            f"{result.message or result.error_code or 'VALIDATION_FAILED'}"
        )
    if not isinstance(result.slide_spec, dict):
        raise GroupASlideGenerationError(
            f"{layout_id} generation returned VALID without a SlideSpec"
        )

    # The platform assigns the stable presentation-local slide id after generation.
    # Work on a defensive copy so the validated generator result and every content/
    # provenance field remain unchanged.
    slide_spec = copy.deepcopy(result.slide_spec)
    slide_spec["slideId"] = f"slide_{order:02d}"
    return slide_spec
