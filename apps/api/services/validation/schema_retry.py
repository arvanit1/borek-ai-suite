"""ES-31 — reject + retry on missing source_refs (orchestration pattern from AT-8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, TypeVar

from services.knowledge_model.source_refs import SourceRefViolation

MAX_SOURCE_REF_RETRIES = 1

PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True)
class SourceRefRetryResult:
    status: Literal["VALID", "VALIDATION_FAILED"]
    payload: Any | None
    attempts: int
    message: str | None = None
    violations: tuple[SourceRefViolation, ...] = ()


class SourceRefRetryError(ValueError):
    """Source refs still invalid after the configured retry budget."""

    def __init__(
        self,
        message: str,
        *,
        violations: list[SourceRefViolation],
        attempts: int,
    ) -> None:
        super().__init__(message)
        self.user_message = message
        self.violations = violations
        self.attempts = attempts


CallFn = Callable[[str | None], PayloadT]
CollectFn = Callable[[PayloadT], list[SourceRefViolation]]


def format_source_ref_feedback(violations: list[SourceRefViolation]) -> str:
    if not violations:
        return ""
    lines = [
        "Every factual chapter and knowledge entry must include source_refs:",
        "- conversation_id (C1, C2, …)",
        "- speaker_role",
        "- excerpt_pointer (turn:<index> from the transcript)",
        "",
        "Fix these locations:",
    ]
    for item in violations[:12]:
        lines.append(f"- {item.path}: {item.message}")
    if len(violations) > 12:
        lines.append(f"- …and {len(violations) - 12} more.")
    return "\n".join(lines)


def run_with_source_ref_retry(
    *,
    call: CallFn[PayloadT],
    collect_violations: CollectFn[PayloadT],
    max_retries: int = MAX_SOURCE_REF_RETRIES,
) -> SourceRefRetryResult:
    """Validate source_refs, retry at least once on failure, then fail loudly."""
    feedback: str | None = None
    attempts = 0
    last_violations: list[SourceRefViolation] = []
    payload: PayloadT | None = None

    while True:
        attempts += 1
        payload = call(feedback)
        last_violations = collect_violations(payload)
        if not last_violations:
            return SourceRefRetryResult(status="VALID", payload=payload, attempts=attempts)
        if attempts > max_retries:
            break
        feedback = format_source_ref_feedback(last_violations)

    return SourceRefRetryResult(
        status="VALIDATION_FAILED",
        payload=None,
        attempts=attempts,
        message=_failure_message(last_violations, attempts),
        violations=tuple(last_violations),
    )


def require_valid_source_refs(
    *,
    call: CallFn[PayloadT],
    collect_violations: CollectFn[PayloadT],
    max_retries: int = MAX_SOURCE_REF_RETRIES,
) -> tuple[PayloadT, int]:
    """Run ``run_with_source_ref_retry`` and raise ``SourceRefRetryError`` on exhaustion."""
    result = run_with_source_ref_retry(
        call=call,
        collect_violations=collect_violations,
        max_retries=max_retries,
    )
    if result.status == "VALID" and result.payload is not None:
        return result.payload, result.attempts
    raise SourceRefRetryError(
        result.message or "Missing or invalid source_refs.",
        violations=list(result.violations),
        attempts=result.attempts,
    )


def _failure_message(violations: list[SourceRefViolation], attempts: int) -> str:
    detail = violations[0].message if violations else "missing source_refs"
    return (
        f"Missing or invalid source_refs after {attempts} attempt"
        f"{'s' if attempts != 1 else ''}: {detail}"
    )
