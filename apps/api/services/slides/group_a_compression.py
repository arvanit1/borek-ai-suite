"""BT-16: Wire Group A constraints into the shared AT-8 compression loop."""

from __future__ import annotations

import copy
from typing import Any, Callable

from services.slides.group_a_constraints import register_group_a_constraints
from services.validation.compression_retry import (
    CompressionResult,
    get_value_at_path,
    set_value_at_path,
    validate_and_compress_slide_spec,
)
from services.validation.constraint_validator import (
    ConstraintViolation,
    LayoutConstraintRegistry,
)

OffendingFieldValues = dict[str, str]
GroupACompressFieldsFn = Callable[
    [OffendingFieldValues, list[ConstraintViolation]],
    OffendingFieldValues,
]


def validate_and_compress_group_a_slide_spec(
    slide_spec: dict[str, Any],
    *,
    compress_fields: GroupACompressFieldsFn,
) -> CompressionResult:
    """Validate a Group A SlideSpec and rewrite only max-length violations.

    ``compress_fields`` is the existing prompt-backed compression callback. It receives
    only a ``path -> value`` map for currently offending text fields plus their AT-7
    violations, and must return rewritten values keyed by those same paths.
    """
    registry = register_group_a_constraints(LayoutConstraintRegistry())
    return validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=_targeted_compressor(compress_fields),
    )


def _targeted_compressor(compress_fields: GroupACompressFieldsFn):
    def compress(
        slide_spec: dict[str, Any],
        violations: list[ConstraintViolation],
    ) -> dict[str, Any]:
        offending_values: OffendingFieldValues = {}
        offending_violations: list[ConstraintViolation] = []
        for violation in violations:
            if violation.code != "max_length":
                continue
            value = get_value_at_path(slide_spec, violation.path)
            if isinstance(value, str):
                offending_values[violation.path] = value
                offending_violations.append(violation)

        rewritten_values = compress_fields(
            copy.deepcopy(offending_values),
            list(offending_violations),
        )

        updated = copy.deepcopy(slide_spec)
        if not isinstance(rewritten_values, dict):
            return updated

        # Ignore unknown paths and non-string responses. The next AT-7 validation pass
        # will keep any unresolved original violation in the retry/failure flow.
        for path in offending_values:
            rewritten = rewritten_values.get(path)
            if isinstance(rewritten, str):
                set_value_at_path(updated, path, rewritten)
        return updated

    return compress
