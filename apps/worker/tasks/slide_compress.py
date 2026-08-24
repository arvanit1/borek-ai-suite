"""AT-8 worker entrypoint for SlideSpec compression/retry."""

from __future__ import annotations

from typing import Any

from services.validation.compression_retry import (
    CompressFn,
    CompressionResult,
    validate_and_compress_slide_spec,
)
from services.validation.constraint_validator import LayoutConstraintRegistry


def run_slide_compression(
    slide_spec: dict[str, Any],
    *,
    registry: LayoutConstraintRegistry,
    compress: CompressFn,
) -> CompressionResult:
    """Run shared AT-8 compression loop for a worker task."""
    return validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=compress,
    )
