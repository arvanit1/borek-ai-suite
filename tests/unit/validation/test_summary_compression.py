"""JJ-23: EXECUTIVE_SUMMARY_01 integration with the shared AT-8 compression loop."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from services.slides.summary_compression import (
    OffendingFieldValues,
    validate_and_compress_summary_slide_spec,
)
from services.validation.constraint_validator import ConstraintViolation

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    ROOT
    / "packages"
    / "contracts"
    / "fixtures"
    / "slide_spec"
    / "summary"
    / "executive_summary_01.minimal.json"
)


def _payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _shorten_to_limits(
    fields: OffendingFieldValues,
    violations: list[ConstraintViolation],
) -> OffendingFieldValues:
    limits = {violation.path: violation.limit for violation in violations}
    return {
        path: value[: limits[path]]
        for path, value in fields.items()
        if isinstance(limits.get(path), int)
    }


def test_valid_executive_summary_skips_compression() -> None:
    calls = {"compress": 0}

    def spy(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        calls["compress"] += 1
        return _shorten_to_limits(fields, violations)

    result = validate_and_compress_summary_slide_spec(
        _payload(),
        compress_fields=spy,
    )
    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert calls["compress"] == 0


def test_overflow_headline_is_compressed() -> None:
    payload = _payload()
    payload["headline"] = "H" * 200
    result = validate_and_compress_summary_slide_spec(
        payload,
        compress_fields=_shorten_to_limits,
    )
    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert len(result.slide_spec["headline"]) <= 180
    assert result.compression_attempts >= 1


def test_unresolved_overflow_fails_closed() -> None:
    payload = _payload()
    payload["headline"] = "H" * 200
    result = validate_and_compress_summary_slide_spec(
        payload,
        compress_fields=lambda fields, _violations: copy.deepcopy(fields),
    )
    assert result.status != "VALID"
