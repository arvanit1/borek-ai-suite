"""AT-8: Compression/retry orchestration for SlideSpec content constraints (technical plan section 15.1)."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Callable, Literal

from services.validation.constraint_validator import (
    ConstraintViolation,
    LayoutConstraintRegistry,
)

MAX_COMPRESSION_ATTEMPTS = 2
CONTENT_CONSTRAINT_EXCEEDED = "CONTENT_CONSTRAINT_EXCEEDED"
COMPRESSIBLE_VIOLATION_CODES = frozenset({"max_length"})

CompressFn = Callable[[dict[str, Any], list[ConstraintViolation]], dict[str, Any]]


@dataclass(frozen=True)
class CompressionResult:
    status: Literal["VALID", "VALIDATION_FAILED"]
    slide_spec: dict[str, Any] | None
    compression_attempts: int
    message: str | None = None
    error_code: str | None = None


def is_compressible_violation(violation: ConstraintViolation) -> bool:
    return violation.code in COMPRESSIBLE_VIOLATION_CODES


def validate_and_compress_slide_spec(
    slide_spec: dict[str, Any],
    *,
    registry: LayoutConstraintRegistry,
    compress: CompressFn,
    max_compression_attempts: int = MAX_COMPRESSION_ATTEMPTS,
) -> CompressionResult:
    """Validate with AT-7, run up to two AI-shortening passes, revalidate after each."""
    if not isinstance(slide_spec, dict):
        return CompressionResult(
            status="VALIDATION_FAILED",
            slide_spec=None,
            compression_attempts=0,
            message="SlideSpec must be an object",
            error_code=CONTENT_CONSTRAINT_EXCEEDED,
        )

    layout_id = slide_spec.get("layoutId")
    if not isinstance(layout_id, str) or not layout_id:
        return _validation_failed(
            slide_spec=None,
            compression_attempts=0,
            layout_id="?",
            reason="SlideSpec.layoutId must be a non-empty string",
        )

    config = registry.get(layout_id)
    if config is None:
        return _validation_failed(
            slide_spec=None,
            compression_attempts=0,
            layout_id=layout_id,
            reason=f"No constraint config registered for layoutId {layout_id!r}",
        )

    current = copy.deepcopy(slide_spec)
    original_source_chapter_ids = copy.deepcopy(current.get("sourceChapterIds"))

    violations = registry.collect_violations(current)
    if not violations:
        return CompressionResult(
            status="VALID",
            slide_spec=current,
            compression_attempts=0,
        )

    if not _violations_are_compressible(violations):
        return _validation_failed(
            slide_spec=None,
            compression_attempts=0,
            layout_id=layout_id,
            reason=_first_non_compressible_message(violations),
        )

    compression_attempts = 0
    while compression_attempts < max_compression_attempts:
        compression_attempts += 1
        current = compress(current, violations)

        if not _source_chapter_ids_preserved(original_source_chapter_ids, current.get("sourceChapterIds")):
            return _validation_failed(
                slide_spec=None,
                compression_attempts=compression_attempts,
                layout_id=layout_id,
                reason="Compression modified sourceChapterIds",
            )

        violations = registry.collect_violations(current)
        if not violations:
            return CompressionResult(
                status="VALID",
                slide_spec=current,
                compression_attempts=compression_attempts,
            )

        if not _violations_are_compressible(violations):
            break

    return _validation_failed(
        slide_spec=None,
        compression_attempts=compression_attempts,
        layout_id=layout_id,
        reason=_compression_exhausted_message(layout_id, violations, compression_attempts),
    )


def _validation_failed(
    *,
    slide_spec: dict[str, Any] | None,
    compression_attempts: int,
    layout_id: str,
    reason: str,
) -> CompressionResult:
    return CompressionResult(
        status="VALIDATION_FAILED",
        slide_spec=slide_spec,
        compression_attempts=compression_attempts,
        message=f"Slide ({layout_id}) {reason}",
        error_code=CONTENT_CONSTRAINT_EXCEEDED,
    )


def _compression_exhausted_message(
    layout_id: str,
    violations: list[ConstraintViolation],
    compression_attempts: int,
) -> str:
    detail = violations[0].message
    return (
        f"{detail} after {compression_attempts} compression attempt"
        f"{'s' if compression_attempts != 1 else ''}"
    )


def _violations_are_compressible(violations: list[ConstraintViolation]) -> bool:
    return bool(violations) and all(is_compressible_violation(v) for v in violations)


def _first_non_compressible_message(violations: list[ConstraintViolation]) -> str:
    for violation in violations:
        if not is_compressible_violation(violation):
            return violation.message
    return violations[0].message


def _source_chapter_ids_preserved(original: Any, updated: Any) -> bool:
    return original == updated


_PATH_TOKEN = re.compile(
    r"([^.\[\]]+)|\[(?:(\d+)|\"([^\"]+)\")\]",
)


def get_value_at_path(payload: dict[str, Any], path: str) -> Any:
    """Resolve dotted/array paths such as phases[0].name for compression helpers."""
    current: Any = payload
    for segment, index, quoted in _parse_path_tokens(path):
        if segment is not None:
            if not isinstance(current, dict) or segment not in current:
                raise KeyError(path)
            current = current[segment]
            continue
        if index is not None:
            if not isinstance(current, list):
                raise KeyError(path)
            current = current[int(index)]
            continue
        if quoted is not None:
            if not isinstance(current, dict) or quoted not in current:
                raise KeyError(path)
            current = current[quoted]
    return current


def set_value_at_path(payload: dict[str, Any], path: str, value: Any) -> None:
    tokens = list(_parse_path_tokens(path))
    if not tokens:
        raise KeyError(path)

    current: Any = payload
    for segment, index, quoted in tokens[:-1]:
        if segment is not None:
            current = current[segment]
        elif index is not None:
            current = current[int(index)]
        else:
            current = current[quoted]  # type: ignore[index]

    last_segment, last_index, last_quoted = tokens[-1]
    if last_segment is not None:
        current[last_segment] = value
    elif last_index is not None:
        current[int(last_index)] = value
    else:
        current[last_quoted] = value  # type: ignore[index]


def _parse_path_tokens(path: str):
    pos = 0
    while pos < len(path):
        if path[pos] == ".":
            pos += 1
            continue
        match = _PATH_TOKEN.match(path, pos)
        if not match:
            raise KeyError(path)
        yield match.group(1), match.group(2), match.group(3)
        pos = match.end()
