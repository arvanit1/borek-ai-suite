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
    last_validation_error: PresentationPlanValidationError | None = None
    last_raw_plan: Any = None

    for attempt in range(3):
        attempt_input = copy.deepcopy(planning_input)
        if last_validation_error is not None:
            attempt_input["instructions"] = _instructions_with_duplicate_correction(
                str(attempt_input.get("instructions") or ""),
                last_validation_error,
            )
        try:
            raw_plan = client.complete_planning(
                planning_input=attempt_input,
                prompt_version=PROMPT_VERSION,
                retry_count=attempt,
            )
        except Exception as exc:
            raise PresentationPlanningCallError(
                f"Presentation planning call failed: {exc}"
            ) from exc
        last_raw_plan = raw_plan

        try:
            return _validated_plan(raw_plan)
        except (SchemaVersionMismatchError, ValidationError, ContractValidationError) as exc:
            last_validation_error = PresentationPlanValidationError(
                f"Invalid PresentationPlan: {exc}"
            )
            if not _is_duplicate_layout_error(exc):
                raise last_validation_error from exc

    if last_raw_plan is not None and last_validation_error is not None:
        try:
            return _validated_plan(_collapse_duplicate_layouts(last_raw_plan))
        except (SchemaVersionMismatchError, ValidationError, ContractValidationError) as exc:
            raise PresentationPlanValidationError(
                f"Invalid PresentationPlan: {exc}"
            ) from exc

    raise last_validation_error or PresentationPlanValidationError(
        "Invalid PresentationPlan: planning retries exhausted"
    )


def _validated_plan(raw_plan: Any) -> PresentationPlan:
    plan = consume_presentation_plan(copy.deepcopy(raw_plan))
    validated_payload = plan.model_dump(mode="json")
    validate_presentation_plan_business_rules(validated_payload)
    validate_registry_layout_selection(validated_payload)
    _validate_unique_layout_ids(validated_payload)
    return plan


def _is_duplicate_layout_error(exc: BaseException) -> bool:
    return "layoutId values must be unique" in str(exc)


def _duplicate_layout_ids_from_error(exc: BaseException) -> list[str]:
    message = str(exc)
    marker = "duplicates:"
    if marker not in message:
        return []
    return [
        part.strip().rstrip(".)")
        for part in message.split(marker, 1)[1].split(",")
        if part.strip()
    ]


def _instructions_with_duplicate_correction(instructions: str, exc: BaseException) -> str:
    duplicates = ", ".join(_duplicate_layout_ids_from_error(exc)) or "the repeated layoutId values"
    return (
        f"{instructions.rstrip()}\n\n"
        "Correction required: the previous PresentationPlan repeated layoutId values. "
        f"Keep {duplicates} at most once. Combine chapter references onto those slides "
        "instead of emitting a second slide with the same layoutId."
    )


def _collapse_duplicate_layouts(raw_plan: Any) -> dict[str, Any]:
    """Keep the first slide per layoutId and merge later chapter references onto it."""
    if not isinstance(raw_plan, dict):
        raise ContractValidationError(
            "PresentationPlan layoutId values must be unique; duplicates could not be repaired"
        )
    collapsed = copy.deepcopy(raw_plan)
    slides = collapsed.get("slides")
    if not isinstance(slides, list):
        return collapsed

    kept: list[dict[str, Any]] = []
    index_by_layout: dict[str, int] = {}
    for slide in slides:
        if not isinstance(slide, dict):
            kept.append(slide)
            continue
        layout_id = slide.get("layoutId")
        if not isinstance(layout_id, str):
            kept.append(copy.deepcopy(slide))
            continue
        if layout_id in index_by_layout:
            existing = kept[index_by_layout[layout_id]]
            existing["frameworkReferences"] = _unique_refs(
                existing.get("frameworkReferences"),
                slide.get("frameworkReferences"),
            )
            continue
        index_by_layout[layout_id] = len(kept)
        kept.append(copy.deepcopy(slide))

    for order, slide in enumerate(kept, start=1):
        if isinstance(slide, dict):
            slide["order"] = order
    collapsed["slides"] = kept
    return collapsed


def _unique_refs(*groups: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, str) or item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _validate_unique_layout_ids(plan: dict[str, Any]) -> None:
    """Fail closed when the one-call planner repeats any slide layout."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for slide in plan.get("slides", []):
        layout_id = slide.get("layoutId")
        if not isinstance(layout_id, str):
            continue
        if layout_id in seen:
            duplicates.add(layout_id)
        seen.add(layout_id)

    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ContractValidationError(
            "PresentationPlan layoutId values must be unique; "
            f"duplicates: {duplicate_list}"
        )


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
