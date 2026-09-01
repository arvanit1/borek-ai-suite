"""AT-42/45: planning job failure message formatting."""

from __future__ import annotations

from services.presentation.planner import PresentationPlanValidationError

from app.services.planning_job_errors import (
    duplicate_layout_ids_from_message,
    enrich_job_error_message,
    format_presentation_planning_failure,
)


def test_duplicate_layout_failure_is_non_retryable_and_actionable() -> None:
    exc = PresentationPlanValidationError(
        "Invalid PresentationPlan: PresentationPlan layoutId values must be unique; "
        "duplicates: PROBLEM_SOLUTION_01, PROCESS_FLOW_01"
    )
    code, message, retryable = format_presentation_planning_failure(exc)
    assert code == "PRESENTATION_PLAN_DUPLICATE_LAYOUTS"
    assert "PROBLEM_SOLUTION_01" in message
    assert "PROCESS_FLOW_01" in message
    assert "unique layout" in message
    assert retryable is False


def test_other_validation_failure_is_non_retryable() -> None:
    exc = PresentationPlanValidationError("Invalid PresentationPlan: order must start at 1")
    code, message, retryable = format_presentation_planning_failure(exc)
    assert code == "PRESENTATION_PLAN_VALIDATION_FAILED"
    assert "order must start at 1" in message
    assert retryable is False


def test_enrich_job_error_message_upgrades_legacy_duplicate_text() -> None:
    legacy = {
        "code": "PRESENTATION_PLANNING_FAILED",
        "message": (
            "Invalid PresentationPlan: PresentationPlan layoutId values must be unique; "
            "duplicates: CONTEXT_01"
        ),
    }
    enriched = enrich_job_error_message(legacy)
    assert "CONTEXT_01" in enriched
    assert "unique layout" in enriched


def test_duplicate_layout_ids_from_message() -> None:
    raw = (
        "Invalid PresentationPlan: PresentationPlan layoutId values must be unique; "
        "duplicates: PROBLEM_SOLUTION_01, PROCESS_FLOW_01"
    )
    assert duplicate_layout_ids_from_message(raw) == [
        "PROBLEM_SOLUTION_01",
        "PROCESS_FLOW_01",
    ]
