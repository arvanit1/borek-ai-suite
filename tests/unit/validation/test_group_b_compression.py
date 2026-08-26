"""JJ-14: Group B integration with the shared AT-8 compression/retry loop."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.group_b_compression import (
    OffendingFieldValues,
    validate_and_compress_group_b_slide_spec,
)
from services.slides.group_b_constraints import GROUP_B_LAYOUT_IDS
from services.validation.compression_retry import (
    CONTENT_CONSTRAINT_EXCEEDED,
    MAX_COMPRESSION_ATTEMPTS,
)
from services.validation.constraint_validator import ConstraintViolation

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"

FIXTURE_NAMES = {
    "PROCESS_FLOW_01": "process_flow_01.minimal.json",
    "TIMELINE_01": "timeline_01.minimal.json",
    "MILESTONES_01": "milestones_01.minimal.json",
    "TEAM_FTE_01": "team_fte_01.minimal.json",
}

OVERFLOW_CASES = {
    "PROCESS_FLOW_01": ("phases[0].description", 80),
    "TIMELINE_01": ("phases[0].name", 28),
    "MILESTONES_01": ("milestones[0].description", 90),
    "TEAM_FTE_01": ("roles[0].responsibility", 80),
}


def _payload(layout_id: str) -> dict:
    return json.loads((FIXTURE_DIR / FIXTURE_NAMES[layout_id]).read_text(encoding="utf-8"))


def _set_path(payload: dict, path: str, value: str) -> None:
    from services.validation.compression_retry import set_value_at_path

    set_value_at_path(payload, path, value)


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


def _noop_compress(
    fields: OffendingFieldValues,
    _violations: list[ConstraintViolation],
) -> OffendingFieldValues:
    return copy.deepcopy(fields)


def test_jj14_valid_group_b_slide_skips_compression() -> None:
    calls = {"compress": 0}

    def spy(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        calls["compress"] += 1
        return _shorten_to_limits(fields, violations)

    original = _payload("PROCESS_FLOW_01")
    result = validate_and_compress_group_b_slide_spec(original, compress_fields=spy)

    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert calls["compress"] == 0
    assert result.slide_spec == original


def test_jj14_first_attempt_fixes_violation() -> None:
    slide_spec = _payload("PROCESS_FLOW_01")
    slide_spec["phases"][0]["description"] = "D" * 81

    result = validate_and_compress_group_b_slide_spec(
        slide_spec,
        compress_fields=_shorten_to_limits,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert result.slide_spec is not None
    assert len(result.slide_spec["phases"][0]["description"]) == 80


def test_jj14_two_failed_attempts_return_validation_failed() -> None:
    calls = {"compress": 0}

    def counting_noop(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        calls["compress"] += 1
        return _noop_compress(fields, violations)

    slide_spec = _payload("TEAM_FTE_01")
    slide_spec["roles"][0]["responsibility"] = "R" * 90

    result = validate_and_compress_group_b_slide_spec(
        slide_spec,
        compress_fields=counting_noop,
    )

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == MAX_COMPRESSION_ATTEMPTS == 2
    assert calls["compress"] == MAX_COMPRESSION_ATTEMPTS
    assert result.slide_spec is None
    assert result.error_code == CONTENT_CONSTRAINT_EXCEEDED


def test_jj14_source_chapter_ids_are_not_changed() -> None:
    received: list[OffendingFieldValues] = []
    slide_spec = _payload("TIMELINE_01")
    slide_spec["title"] = "T" * 73
    original_sources = copy.deepcopy(slide_spec["sourceChapterIds"])

    def malicious_response(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        received.append(copy.deepcopy(fields))
        rewritten = _shorten_to_limits(fields, violations)
        rewritten["sourceChapterIds"] = "changed"
        return rewritten

    result = validate_and_compress_group_b_slide_spec(
        slide_spec,
        compress_fields=malicious_response,
    )

    assert received == [{"title": "T" * 73}]
    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["sourceChapterIds"] == original_sources


def test_jj14_item_count_violation_fails_without_deleting_items() -> None:
    calls = {"compress": 0}
    slide_spec = _payload("PROCESS_FLOW_01")
    slide_spec["phases"] = [
        {"number": index + 1, "name": f"Step {index}", "description": "Phase"}
        for index in range(9)
    ]
    original = copy.deepcopy(slide_spec)

    def spy(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        calls["compress"] += 1
        return _shorten_to_limits(fields, violations)

    result = validate_and_compress_group_b_slide_spec(
        slide_spec,
        compress_fields=spy,
    )

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 0
    assert result.slide_spec is None
    assert calls["compress"] == 0
    assert slide_spec == original
    assert len(slide_spec["phases"]) == 9


@pytest.mark.parametrize("layout_id", GROUP_B_LAYOUT_IDS)
def test_jj14_all_group_b_layouts_enter_shared_flow(layout_id: str) -> None:
    path, limit = OVERFLOW_CASES[layout_id]
    slide_spec = _payload(layout_id)
    _set_path(slide_spec, path, "X" * (limit + 1))

    result = validate_and_compress_group_b_slide_spec(
        slide_spec,
        compress_fields=_shorten_to_limits,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 1
