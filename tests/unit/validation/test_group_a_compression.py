"""BT-16: Group A integration with the shared AT-8 compression/retry loop."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.group_a_compression import (
    OffendingFieldValues,
    validate_and_compress_group_a_slide_spec,
)
from services.slides.group_a_constraints import GROUP_A_LAYOUT_IDS
from services.validation.compression_retry import (
    CONTENT_CONSTRAINT_EXCEEDED,
    MAX_COMPRESSION_ATTEMPTS,
)
from services.validation.constraint_validator import ConstraintViolation

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"

FIXTURE_NAMES = {
    "COVER_01": "cover_01.minimal.json",
    "CONTEXT_01": "context_01.minimal.json",
    "PROBLEM_SOLUTION_01": "problem_solution_01.minimal.json",
    "SCOPE_01": "scope_01.minimal.json",
    "REQUIREMENTS_MATRIX_01": "requirements_matrix_01.minimal.json",
}

OVERFLOW_CASES = {
    "COVER_01": ("title", 60),
    "CONTEXT_01": ("problem.description", 160),
    "PROBLEM_SOLUTION_01": ("solution.description", 220),
    "SCOPE_01": ("included[0]", 72),
    "REQUIREMENTS_MATRIX_01": ("requirements[0].title", 48),
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


def test_bt16_valid_group_a_slide_skips_compression() -> None:
    calls = {"compress": 0}

    def spy(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        calls["compress"] += 1
        return _shorten_to_limits(fields, violations)

    original = _payload("COVER_01")
    result = validate_and_compress_group_a_slide_spec(original, compress_fields=spy)

    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert calls["compress"] == 0
    assert result.slide_spec == original


def test_bt16_first_attempt_fixes_violation() -> None:
    slide_spec = _payload("CONTEXT_01")
    slide_spec["problem"]["description"] = "D" * 161

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=_shorten_to_limits,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert result.slide_spec is not None
    assert len(result.slide_spec["problem"]["description"]) == 160


def test_bt16_first_attempt_fails_second_succeeds() -> None:
    attempts = {"count": 0}

    def shorten_one_character(
        fields: OffendingFieldValues,
        _violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        attempts["count"] += 1
        return {path: value[:-1] for path, value in fields.items()}

    slide_spec = _payload("PROBLEM_SOLUTION_01")
    slide_spec["solution"]["description"] = "D" * 222

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=shorten_one_character,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 2
    assert attempts["count"] == 2


def test_bt16_two_failed_attempts_return_validation_failed() -> None:
    calls = {"compress": 0}

    def counting_noop(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        calls["compress"] += 1
        return _noop_compress(fields, violations)

    slide_spec = _payload("SCOPE_01")
    slide_spec["included"][0] = "I" * 80

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=counting_noop,
    )

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == MAX_COMPRESSION_ATTEMPTS == 2
    assert calls["compress"] == MAX_COMPRESSION_ATTEMPTS
    assert result.slide_spec is None
    assert result.error_code == CONTENT_CONSTRAINT_EXCEEDED


def test_bt16_layout_and_source_chapter_ids_are_not_exposed_or_changed() -> None:
    received: list[OffendingFieldValues] = []
    slide_spec = _payload("COVER_01")
    slide_spec["title"] = "T" * 61
    original_layout_id = slide_spec["layoutId"]
    original_sources = copy.deepcopy(slide_spec["sourceChapterIds"])

    def malicious_response(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        received.append(copy.deepcopy(fields))
        rewritten = _shorten_to_limits(fields, violations)
        rewritten["layoutId"] = "SCOPE_01"
        rewritten["sourceChapterIds"] = "changed"
        return rewritten

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=malicious_response,
    )

    assert received == [{"title": "T" * 61}]
    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["layoutId"] == original_layout_id
    assert result.slide_spec["sourceChapterIds"] == original_sources


def test_bt16_non_offending_fields_are_preserved() -> None:
    slide_spec = _payload("REQUIREMENTS_MATRIX_01")
    slide_spec["requirements"][0]["title"] = "R" * 49
    original = copy.deepcopy(slide_spec)

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=_shorten_to_limits,
    )

    assert result.status == "VALID"
    assert result.slide_spec is not None
    expected = copy.deepcopy(original)
    expected["requirements"][0]["title"] = "R" * 48
    assert result.slide_spec == expected


def test_bt16_only_offending_fields_are_sent_for_compression() -> None:
    received: list[tuple[OffendingFieldValues, list[str]]] = []
    slide_spec = _payload("COVER_01")
    slide_spec["title"] = "T" * 61
    slide_spec["subtitle"] = "S" * 101

    def recording_compress(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        received.append((copy.deepcopy(fields), [violation.path for violation in violations]))
        return _shorten_to_limits(fields, violations)

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=recording_compress,
    )

    assert result.status == "VALID"
    assert received == [
        (
            {"title": "T" * 61, "subtitle": "S" * 101},
            ["title", "subtitle"],
        )
    ]


def test_bt16_structural_item_count_violation_fails_without_deleting_items() -> None:
    calls = {"compress": 0}
    slide_spec = _payload("COVER_01")
    slide_spec["statBadges"] = [
        {"value": str(index), "label": f"Badge {index}"} for index in range(4)
    ]
    original = copy.deepcopy(slide_spec)

    def spy(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        calls["compress"] += 1
        return _shorten_to_limits(fields, violations)

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=spy,
    )

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 0
    assert result.slide_spec is None
    assert calls["compress"] == 0
    assert slide_spec == original
    assert len(slide_spec["statBadges"]) == 4


@pytest.mark.parametrize("layout_id", GROUP_A_LAYOUT_IDS)
def test_bt16_all_group_a_layouts_enter_shared_flow(layout_id: str) -> None:
    path, limit = OVERFLOW_CASES[layout_id]
    slide_spec = _payload(layout_id)
    _set_path(slide_spec, path, "X" * (limit + 1))

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=_shorten_to_limits,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 1


def test_bt16_compression_result_is_revalidated_by_at7() -> None:
    attempts = {"count": 0}
    slide_spec = _payload("CONTEXT_01")
    slide_spec["problem"]["description"] = "D" * 162

    def first_still_invalid_then_valid(
        fields: OffendingFieldValues,
        violations: list[ConstraintViolation],
    ) -> OffendingFieldValues:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return {path: value[:-1] for path, value in fields.items()}
        return _shorten_to_limits(fields, violations)

    result = validate_and_compress_group_a_slide_spec(
        slide_spec,
        compress_fields=first_still_invalid_then_valid,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 2
    assert attempts["count"] == 2
