"""One-call Presentation Planner from a confirmed FrameworkObject."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from generated.python.contracts.framework_object import Status
from generated.python.contracts.presentation_plan import PresentationPlan
from llm.ci_prompt import with_ci_prompt
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
    chapter_split_framework_references,
    chapter_split_layout_slots,
    prepare_chapter_layout_guidance_for_planner,
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
    planning_input_base = {
        "instructions": with_ci_prompt(PROMPT_PATH.read_text(encoding="utf-8")),
        "frameworkObject": framework_payload,
        "chapterLayoutGuidance": prepare_chapter_layout_guidance_for_planner(),
        "targetSchema": planning_target_schema(),
    }
    client = planner if planner is not None else LlmClient()
    last_validation_error: PresentationPlanValidationError | None = None
    duplicate_layout_ids: list[str] = []
    previous_invalid_plan: dict[str, Any] | None = None

    for attempt in range(3):
        planning_input = _planning_input_for_attempt(
            planning_input_base,
            attempt=attempt,
            duplicate_layout_ids=duplicate_layout_ids,
            previous_invalid_plan=previous_invalid_plan,
        )
        try:
            raw_plan = client.complete_planning(
                planning_input=planning_input,
                prompt_version=PROMPT_VERSION,
                retry_count=attempt,
            )
        except Exception as exc:
            raise PresentationPlanningCallError(
                f"Presentation planning call failed: {exc}"
            ) from exc

        candidate_plans = [copy.deepcopy(raw_plan)]
        duplicate_ids = duplicate_layout_ids_from_plan(raw_plan)
        if duplicate_ids:
            repaired = repair_chapter_split_duplicate_layouts(raw_plan)
            if repaired is not None:
                candidate_plans.insert(0, repaired)

        for candidate in candidate_plans:
            try:
                return _validate_plan_candidate(candidate)
            except PresentationPlanValidationError as exc:
                last_validation_error = exc
                if not _is_duplicate_layout_error(exc):
                    raise
                duplicate_layout_ids = duplicate_layout_ids_from_plan(candidate)
                previous_invalid_plan = copy.deepcopy(raw_plan)
                break
        else:
            continue

        if attempt == 2:
            raise last_validation_error from None

    raise last_validation_error or PresentationPlanValidationError(
        "Invalid PresentationPlan: planning retries exhausted"
    )


def _planning_input_for_attempt(
    planning_input_base: dict[str, Any],
    *,
    attempt: int,
    duplicate_layout_ids: list[str],
    previous_invalid_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    planning_input = copy.deepcopy(planning_input_base)
    if attempt == 0 or not duplicate_layout_ids:
        return planning_input

    planning_input["retryValidationErrors"] = {
        "duplicateLayoutIds": duplicate_layout_ids,
        "message": (
            "Each layoutId may appear at most once in the PresentationPlan. "
            "Do not emit additional slides with the listed layoutIds. "
            "Merge or fold the relevant chapter content into the single intended "
            "slide for each layout."
        ),
    }
    planning_input["forbiddenDuplicateLayoutIds"] = duplicate_layout_ids
    if previous_invalid_plan is not None:
        planning_input["previousInvalidPlan"] = copy.deepcopy(previous_invalid_plan)
    return planning_input


def _validate_plan_candidate(raw_plan: dict[str, Any]) -> PresentationPlan:
    try:
        plan = consume_presentation_plan(copy.deepcopy(raw_plan))
        validated_payload = plan.model_dump(mode="json")
        validate_presentation_plan_business_rules(validated_payload)
        validate_registry_layout_selection(validated_payload)
        _validate_unique_layout_ids(validated_payload)
        return plan
    except (SchemaVersionMismatchError, ValidationError, ContractValidationError) as exc:
        raise PresentationPlanValidationError(
            f"Invalid PresentationPlan: {exc}"
        ) from exc


def duplicate_layout_ids_from_plan(plan: dict[str, Any]) -> list[str]:
    """Return sorted duplicate layoutId values present in a planner response."""
    if not isinstance(plan, dict):
        return []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for slide in plan.get("slides", []):
        if not isinstance(slide, dict):
            continue
        layout_id = slide.get("layoutId")
        if not isinstance(layout_id, str):
            continue
        if layout_id in seen:
            duplicates.add(layout_id)
        seen.add(layout_id)
    return sorted(duplicates)


def repair_chapter_split_duplicate_layouts(plan: dict[str, Any]) -> dict[str, Any] | None:
    """Merge split duplicates for multi-chapter layout slots defined in BT-3 guidance."""
    if not isinstance(plan, dict):
        return None

    duplicate_ids = duplicate_layout_ids_from_plan(plan)
    if not duplicate_ids:
        return None

    repairable_layouts: set[str] = set()
    allowed_references: set[str] = set()
    for chapters, layout_ids in chapter_split_layout_slots().items():
        if layout_ids & set(duplicate_ids):
            repairable_layouts.update(layout_ids)
            allowed_references.update(chapter_split_framework_references(chapters))

    if not repairable_layouts or not all(
        layout_id in repairable_layouts for layout_id in duplicate_ids
    ):
        return None

    slides = plan.get("slides")
    if not isinstance(slides, list):
        return None

    repaired = copy.deepcopy(plan)
    repaired_slides: list[dict[str, Any]] = []
    merged_by_layout: dict[str, dict[str, Any]] = {}

    for slide in slides:
        if not isinstance(slide, dict):
            return None
        layout_id = slide.get("layoutId")
        references = slide.get("frameworkReferences")
        if (
            not isinstance(layout_id, str)
            or layout_id not in duplicate_ids
            or not isinstance(references, list)
            or not references
            or not all(
                isinstance(reference, str) and reference in allowed_references
                for reference in references
            )
        ):
            repaired_slides.append(copy.deepcopy(slide))
            continue

        existing = merged_by_layout.get(layout_id)
        if existing is None:
            merged = copy.deepcopy(slide)
            merged["frameworkReferences"] = sorted(set(references))
            merged_by_layout[layout_id] = merged
            repaired_slides.append(merged)
            continue

        merged_references = sorted(
            set(existing.get("frameworkReferences", [])) | set(references)
        )
        existing["frameworkReferences"] = merged_references

    for order, slide in enumerate(repaired_slides, start=1):
        slide["order"] = order

    repaired["slides"] = repaired_slides
    if duplicate_layout_ids_from_plan(repaired):
        return None
    return repaired


def _is_duplicate_layout_error(exc: BaseException) -> bool:
    return "layoutId values must be unique" in str(exc)


def _validate_unique_layout_ids(plan: dict[str, Any]) -> None:
    """Fail closed when the one-call planner repeats any slide layout."""
    duplicates = duplicate_layout_ids_from_plan(plan)
    if duplicates:
        duplicate_list = ", ".join(duplicates)
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
