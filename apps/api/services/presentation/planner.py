"""One-call Presentation Planner from a confirmed FrameworkObject."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from generated.python.contracts.framework_object import Status
from generated.python.contracts.presentation_plan import PresentationPlan
from llm.client import LlmClient, load_prompt_version
from packages.contracts.schema_consumer import (
    SchemaVersionMismatchError,
    consume_framework_object,
    consume_presentation_plan,
)
from packages.contracts.validators import (
    ContractValidationError,
    validate_presentation_plan_business_rules,
)
from services.presentation.chapter_layout_guidance import (
    load_chapter_layout_guidance,
)
from services.presentation.generatable_layouts import planning_target_schema
from services.presentation.registry_validation import (
    validate_registry_layout_selection,
)

PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "llm"
    / "openai"
    / "prompts"
    / "presentation_planner_v2.txt"
)
PROMPT_VERSION = load_prompt_version(str(PROMPT_PATH))


class PresentationPlannerError(RuntimeError):
    """Base error for BT-1 planning failures."""


class FrameworkObjectValidationError(PresentationPlannerError):
    """The planner input does not satisfy the canonical FrameworkObject contract."""


class FrameworkNotConfirmedError(PresentationPlannerError):
    """Stage B cannot start from an unconfirmed FrameworkObject."""


class PresentationPlanningCallError(PresentationPlannerError):
    """The injected planning client failed before producing a result."""


class PresentationPlanValidationError(PresentationPlannerError):
    """The planning result does not satisfy the canonical PresentationPlan contract."""


class PlanningClient(Protocol):
    def complete_planning(
        self,
        *,
        planning_input: dict[str, Any] | None = None,
        prompt_version: str = "v1",
        retry_count: int = 0,
    ) -> dict[str, Any]: ...


def plan_presentation(
    confirmed_framework: dict[str, Any],
    *,
    planner: PlanningClient | None = None,
) -> PresentationPlan:
    """Create one validated PresentationPlan from one confirmed FrameworkObject."""
    framework_payload = _confirmed_framework_payload(confirmed_framework)
    planning_input = {
        "instructions": PROMPT_PATH.read_text(encoding="utf-8"),
        "frameworkObject": framework_payload,
        "chapterLayoutGuidance": load_chapter_layout_guidance(),
        "targetSchema": planning_target_schema(),
    }
    client = planner if planner is not None else LlmClient()

    try:
        raw_plan = client.complete_planning(
            planning_input=planning_input,
            prompt_version=PROMPT_VERSION,
            retry_count=0,
        )
    except Exception as exc:
        raise PresentationPlanningCallError(
            f"Presentation planning call failed: {exc}"
        ) from exc

    try:
        plan = consume_presentation_plan(copy.deepcopy(raw_plan))
        validated_payload = plan.model_dump(mode="json")
        validate_presentation_plan_business_rules(validated_payload)
        validate_registry_layout_selection(validated_payload)
    except (SchemaVersionMismatchError, ValidationError, ContractValidationError) as exc:
        raise PresentationPlanValidationError(
            f"Invalid PresentationPlan: {exc}"
        ) from exc
    return plan


def _confirmed_framework_payload(framework: Any) -> dict[str, Any]:
    try:
        validated = consume_framework_object(copy.deepcopy(framework))
    except (SchemaVersionMismatchError, ValidationError) as exc:
        raise FrameworkObjectValidationError(
            f"Invalid FrameworkObject: {exc}"
        ) from exc
    if validated.status is not Status.confirmed:
        raise FrameworkNotConfirmedError(
            "Stage B requires FrameworkObject.status='confirmed'"
        )
    return validated.model_dump(mode="json")
