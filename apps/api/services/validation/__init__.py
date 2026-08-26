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
from services.validation.schema_retry import (
    MAX_SOURCE_REF_RETRIES,
    SourceRefRetryError,
    SourceRefRetryResult,
    format_source_ref_feedback,
    require_valid_source_refs,
    run_with_source_ref_retry,
)

__all__ = [
    "CONTENT_CONSTRAINT_EXCEEDED",
    "MAX_COMPRESSION_ATTEMPTS",
    "MAX_SOURCE_REF_RETRIES",
    "CompressionResult",
    "ConstraintValidationError",
    "ConstraintViolation",
    "LayoutConstraintRegistry",
    "SourceRefRetryError",
    "SourceRefRetryResult",
    "collect_constraint_violations",
    "format_source_ref_feedback",
    "require_valid_source_refs",
    "run_with_source_ref_retry",
    "validate_against_constraints",
    "validate_and_compress_slide_spec",
]
