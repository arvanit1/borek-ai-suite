"""AT-owned Stage B provider registration.

This module supplies deterministic fixture callbacks when
``AI_EXECUTION_MODE=fixture`` and the live OpenAI planning, structured-generation,
and compression clients when mode is ``live``. Live mode has no fixture fallback.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.config import settings
from llm.client import LlmClient, load_prompt_version
from llm.live_slide_repair import wrap_live_structured_generator
from services.presentation.planner import PlanningClient
from services.slides.content_generation.group_a.common import StructuredGenerator
from services.slides.group_a_compression import GroupACompressFieldsFn

_COMPRESSION_PROMPT_PATH = (
    Path(__file__).resolve().parents[5]
    / "apps"
    / "api"
    / "llm"
    / "openai"
    / "prompts"
    / "slide_compression_v1.txt"
)
_COMPRESSION_PROMPT_VERSION = load_prompt_version(str(_COMPRESSION_PROMPT_PATH))

_REPO_ROOT = Path(__file__).resolve().parents[5]
_GROUP_A_FIXTURE_DIR = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"
)
_GROUP_B_FIXTURE_DIR = (
    _REPO_ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"
)
_GROUP_C_FIXTURE_DIR = _REPO_ROOT / "packages" / "contracts" / "fixtures" / "slide_spec"

_LAYOUT_FIXTURES = {
    "COVER_01": _GROUP_A_FIXTURE_DIR / "cover_01.realistic.json",
    "CONTEXT_01": _GROUP_A_FIXTURE_DIR / "context_01.realistic.json",
    "PROBLEM_SOLUTION_01": _GROUP_A_FIXTURE_DIR / "problem_solution_01.realistic.json",
    "SCOPE_01": _GROUP_A_FIXTURE_DIR / "scope_01.realistic.json",
    "REQUIREMENTS_MATRIX_01": _GROUP_A_FIXTURE_DIR / "requirements_matrix_01.realistic.json",
    "PROCESS_FLOW_01": _GROUP_B_FIXTURE_DIR / "process_flow_01.realistic.json",
    "TIMELINE_01": _GROUP_B_FIXTURE_DIR / "timeline_01.realistic.json",
    "MILESTONES_01": _GROUP_B_FIXTURE_DIR / "milestones_01.realistic.json",
    "TEAM_FTE_01": _GROUP_B_FIXTURE_DIR / "team_fte_01.realistic.json",
    "ARCHITECTURE_01": _GROUP_C_FIXTURE_DIR / "architecture_01.minimal.json",
    "COMPLIANCE_01": _GROUP_C_FIXTURE_DIR / "compliance_01.minimal.json",
    "SUCCESS_METRICS_01": _GROUP_C_FIXTURE_DIR / "success_metrics_01.minimal.json",
    "OPEN_QUESTIONS_01": _GROUP_C_FIXTURE_DIR / "open_questions_01.minimal.json",
    "NEXT_STEPS_01": _GROUP_C_FIXTURE_DIR / "next_steps_01.minimal.json",
}


_FIXTURE_PLAN = {
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


class FixturePlanningClient:
    def complete_planning(self, **_kwargs: Any) -> dict[str, Any]:
        return copy.deepcopy(_FIXTURE_PLAN)


def _live_llm_client() -> LlmClient:
    """Build the shared OpenAI-backed client without affecting fixture execution."""
    from llm.openai_executor import OpenAIResponsesExecutor

    api_key = settings.OPENAI_API_KEY.strip()
    if not api_key:
        from llm.openai_executor import OpenAIProviderConfigurationError

        raise OpenAIProviderConfigurationError(
            "OPENAI_API_KEY is required when AI_EXECUTION_MODE=live"
        )
    model = settings.OPENAI_PRESENTATION_MODEL.strip()
    executor = OpenAIResponsesExecutor(api_key=api_key, model=model)
    return LlmClient(model=model, executor=executor)


def build_live_planning_client() -> PlanningClient:
    """Build BT-1's OpenAI-backed client without affecting fixture execution."""
    return _live_llm_client()


def build_live_structured_generator() -> StructuredGenerator:
    """Build the live structured-output callback used by every layout generator."""
    return wrap_live_structured_generator(
        _live_llm_client().structured_generator(prompt_version="slide_structured_v1")
    )


def build_live_compression_fields() -> GroupACompressFieldsFn:
    """Build the live AT-8 compression callback used by every layout generator."""
    return _live_llm_client().compression_fields_fn(
        prompt_version=_COMPRESSION_PROMPT_VERSION,
        instructions=_COMPRESSION_PROMPT_PATH.read_text(encoding="utf-8"),
    )


def get_runtime_planning_client() -> PlanningClient:
    """Select deterministic fixture planning or live OpenAI planning by mode."""
    if settings.AI_EXECUTION_MODE == "fixture":
        return FixturePlanningClient()
    return build_live_planning_client()


def get_runtime_structured_generator() -> StructuredGenerator:
    """Select deterministic fixture slides or live OpenAI slide generation by mode."""
    if settings.AI_EXECUTION_MODE == "fixture":
        return fixture_structured_generate
    return build_live_structured_generator()


def get_runtime_compression_fields() -> GroupACompressFieldsFn:
    """Select deterministic fixture compression or live OpenAI compression by mode."""
    if settings.AI_EXECUTION_MODE == "fixture":
        return fixture_compress_fields
    return build_live_compression_fields()


def fixture_structured_generate(request: Any) -> dict[str, Any]:
    path = _LAYOUT_FIXTURES.get(getattr(request, "layout_id", ""))
    if path is None or not path.is_file():
        raise RuntimeError(f"No fixture provider for layout {getattr(request, 'layout_id', None)}")
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_compress_fields(
    offending: dict[str, str],
    violations: list[Any],
) -> dict[str, str]:
    limits = {violation.path: violation.limit for violation in violations}
    return {
        path: value[: limits[path]] if isinstance(limits.get(path), int) else value
        for path, value in offending.items()
    }


def install_runtime_stage_b_providers() -> None:
    """Register fixture or live Stage B callbacks for the configured execution mode."""
    from app.services import stage_b_orchestration

    stage_b_orchestration.get_live_structured_generator = (  # type: ignore[method-assign]
        get_runtime_structured_generator
    )
    stage_b_orchestration.get_live_compression_fields = (  # type: ignore[method-assign]
        get_runtime_compression_fields
    )
