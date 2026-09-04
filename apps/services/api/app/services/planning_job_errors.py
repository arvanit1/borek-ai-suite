"""AT-42/45: user-facing messages for presentation planning job failures."""

from __future__ import annotations

import re
from typing import Any

from services.presentation.planner import PresentationPlanValidationError

_DUPLICATE_LAYOUTS_RE = re.compile(
    r"layoutId values must be unique;\s*duplicates:\s*(.+?)(?:\)|$)",
    re.IGNORECASE,
)


def format_presentation_planning_failure(exc: BaseException) -> tuple[str, str, bool]:
    """Return (error_code, message, retryable) for a planning worker failure."""
    if isinstance(exc, PresentationPlanValidationError):
        return _validation_failure(str(exc))
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        code = str(getattr(current, "code", "") or "")
        if code == "EGRESS_BLOCKED":
            return "EGRESS_BLOCKED", str(current), False
        current = current.__cause__
    code = str(getattr(exc, "code", "") or "PRESENTATION_PLANNING_FAILED")
    retryable = bool(getattr(exc, "retryable", True))
    return code, str(exc), retryable


def _validation_failure(raw: str) -> tuple[str, str, bool]:
    detail = raw.removeprefix("Invalid PresentationPlan: ").strip()
    match = _DUPLICATE_LAYOUTS_RE.search(detail)
    if match:
        duplicates = match.group(1).strip().rstrip(".")
        return (
            "PRESENTATION_PLAN_DUPLICATE_LAYOUTS",
            (
                "The AI planner assigned the same slide layout more than once "
                f"({duplicates}). Each slide must use a unique layout. "
                "Try Generate plan again; if the error persists, the planning "
                "prompt needs adjustment (BT-1)."
            ),
            False,
        )
    return (
        "PRESENTATION_PLAN_VALIDATION_FAILED",
        f"Presentation plan validation failed: {detail}",
        False,
    )


def duplicate_layout_ids_from_message(message: str) -> list[str]:
    """Extract duplicate layout ids from a stored job error message."""
    match = _DUPLICATE_LAYOUTS_RE.search(message)
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


def enrich_job_error_message(error: dict[str, Any] | None) -> str:
    """Upgrade legacy stored messages when surfacing failed jobs to clients."""
    if not error:
        return "Generation job failed"
    message = str(error.get("message") or "Generation job failed")
    code = str(error.get("code") or "")
    if code == "PRESENTATION_PLAN_DUPLICATE_LAYOUTS":
        return message
    if "layoutId values must be unique" in message:
        _, friendly, _ = _validation_failure(message)
        return friendly
    return message
