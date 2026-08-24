"""Validation services (AT-7+)."""

from services.validation.compression_retry import (
    CONTENT_CONSTRAINT_EXCEEDED,
    MAX_COMPRESSION_ATTEMPTS,
    CompressionResult,
    validate_and_compress_slide_spec,
)
from services.validation.constraint_validator import (
    ConstraintValidationError,
    ConstraintViolation,
    LayoutConstraintRegistry,
    collect_constraint_violations,
    validate_against_constraints,
)

__all__ = [
    "CONTENT_CONSTRAINT_EXCEEDED",
    "MAX_COMPRESSION_ATTEMPTS",
    "CompressionResult",
    "ConstraintValidationError",
    "ConstraintViolation",
    "LayoutConstraintRegistry",
    "collect_constraint_violations",
    "validate_against_constraints",
    "validate_and_compress_slide_spec",
]
