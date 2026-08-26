"""AT-8: compression/retry mechanism tests."""

from __future__ import annotations

import copy

import pytest

from services.validation.compression_retry import (
    CONTENT_CONSTRAINT_EXCEEDED,
    MAX_COMPRESSION_ATTEMPTS,
    CompressionResult,
    get_value_at_path,
    is_compressible_violation,
    set_value_at_path,
    validate_and_compress_slide_spec,
)
from services.validation.constraint_validator import (
    ConstraintViolation,
    LayoutConstraintRegistry,
)

TIMELINE_01_CONSTRAINT_CONFIG = {
    "properties": {
        "title": {"required": True, "type": "string", "max_length": 120},
        "sourceChapterIds": {"required": True, "type": "array", "min_items": 1},
        "phases": {
            "required": True,
            "type": "array",
            "min_items": 2,
            "max_items": 8,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"required": True, "type": "string", "max_length": 28},
                    "description": {"type": "string", "max_length": 75},
                },
            },
        },
    }
}


@pytest.fixture
def registry() -> LayoutConstraintRegistry:
    reg = LayoutConstraintRegistry()
    reg.register("TIMELINE_01", TIMELINE_01_CONSTRAINT_CONFIG)
    return reg


def _shorten_to_limits(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
    """Test double for AI shortening: trim max_length violations to their limits."""
    updated = copy.deepcopy(slide_spec)
    for violation in violations:
        if violation.code != "max_length" or violation.limit is None:
            continue
        current_value = get_value_at_path(updated, violation.path)
        if isinstance(current_value, str) and len(current_value) > violation.limit:
            set_value_at_path(updated, violation.path, current_value[: violation.limit])
    return updated


def _noop_compress(slide_spec: dict, _violations: list[ConstraintViolation]) -> dict:
    return copy.deepcopy(slide_spec)


def test_at8_valid_slide_spec_passes_without_compression(registry: LayoutConstraintRegistry) -> None:
    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "Phase A", "description": "First"},
            {"name": "Phase B", "description": "Second"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=_shorten_to_limits,
    )
    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert result.slide_spec is not None


def test_at8_single_compression_pass_then_valid(registry: LayoutConstraintRegistry) -> None:
    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=_shorten_to_limits,
    )
    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert result.slide_spec is not None
    assert len(result.slide_spec["phases"][0]["name"]) == 28


def test_at8_two_compression_passes_then_valid(registry: LayoutConstraintRegistry) -> None:
    attempts = {"count": 0}

    def compress_one_char_per_attempt(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        attempts["count"] += 1
        updated = copy.deepcopy(slide_spec)
        for violation in violations:
            if violation.code != "max_length":
                continue
            value = get_value_at_path(updated, violation.path)
            if isinstance(value, str) and len(value) > 1:
                set_value_at_path(updated, violation.path, value[:-1])
        return updated

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 30, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=compress_one_char_per_attempt,
    )
    assert result.status == "VALID"
    assert result.compression_attempts == 2
    assert attempts["count"] == 2


def test_at8_validation_failed_after_two_attempts(registry: LayoutConstraintRegistry) -> None:
    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 40, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=_noop_compress,
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == MAX_COMPRESSION_ATTEMPTS
    assert result.slide_spec is None
    assert result.error_code == CONTENT_CONSTRAINT_EXCEEDED
    assert result.message is not None
    assert "after 2 compression attempts" in result.message


def test_at8_non_compressible_violation_fails_without_retry(registry: LayoutConstraintRegistry) -> None:
    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [{"name": "Only one", "description": "x"}],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=_shorten_to_limits,
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 0
    assert result.slide_spec is None
    assert "below minimum" in (result.message or "")


def test_at8_source_chapter_ids_must_remain_unchanged(registry: LayoutConstraintRegistry) -> None:
    def bad_compress(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        updated = _shorten_to_limits(slide_spec, violations)
        updated["sourceChapterIds"] = ["99"]
        return updated

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=bad_compress,
    )
    assert result.status == "VALIDATION_FAILED"
    assert "sourceChapterIds" in (result.message or "")


def test_at8_field_provenance_must_remain_unchanged(
    registry: LayoutConstraintRegistry,
) -> None:
    def bad_compress(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        updated = _shorten_to_limits(slide_spec, violations)
        updated["fieldProvenance"][0]["sourceChapterIds"] = ["9"]
        return updated

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "fieldProvenance": [
            {"path": "phases[0].name", "sourceChapterIds": ["10"]}
        ],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=bad_compress,
    )

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 1
    assert "fieldProvenance" in (result.message or "")


def test_at8_compression_cannot_add_field_provenance(
    registry: LayoutConstraintRegistry,
) -> None:
    def bad_compress(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        updated = _shorten_to_limits(slide_spec, violations)
        updated["fieldProvenance"] = [
            {"path": "phases[0].name", "sourceChapterIds": ["10"]}
        ]
        return updated

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=bad_compress,
    )

    assert result.status == "VALIDATION_FAILED"
    assert "fieldProvenance" in (result.message or "")


def test_at8_does_not_return_silently_truncated_invalid_spec(registry: LayoutConstraintRegistry) -> None:
    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 40, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=_noop_compress,
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.slide_spec is None


def test_at8_revalidates_with_at7_after_each_compression(registry: LayoutConstraintRegistry) -> None:
    calls = {"validate": 0}
    original_collect = registry.collect_violations

    def counting_collect(slide_spec: dict):
        calls["validate"] += 1
        return original_collect(slide_spec)

    registry.collect_violations = counting_collect  # type: ignore[method-assign]

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=_shorten_to_limits,
    )
    assert result.status == "VALID"
    assert calls["validate"] == 2


def test_at8_compress_never_called_when_valid_on_first_pass(registry: LayoutConstraintRegistry) -> None:
    calls = {"compress": 0}

    def spy_compress(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        calls["compress"] += 1
        return _shorten_to_limits(slide_spec, violations)

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "Phase A", "description": "First"},
            {"name": "Phase B", "description": "Second"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=spy_compress,
    )
    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert calls["compress"] == 0


def test_at8_compress_receives_max_length_violations_for_targeting(registry: LayoutConstraintRegistry) -> None:
    received: list[list[ConstraintViolation]] = []

    def recording_compress(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        received.append(list(violations))
        return _shorten_to_limits(slide_spec, violations)

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=recording_compress,
    )
    assert result.status == "VALID"
    assert len(received) == 1
    assert all(is_compressible_violation(v) for v in received[0])
    assert received[0][0].code == "max_length"
    assert received[0][0].path == "phases[0].name"
    assert received[0][0].limit == 28


def test_at8_mixed_compressible_and_non_compressible_violations_fail_without_retry(
    registry: LayoutConstraintRegistry,
) -> None:
    calls = {"compress": 0}

    def spy_compress(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        calls["compress"] += 1
        return _shorten_to_limits(slide_spec, violations)

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [{"name": "A" * 29, "description": "ok"}],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=spy_compress,
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 0
    assert result.slide_spec is None
    assert calls["compress"] == 0
    assert "below minimum" in (result.message or "")


def test_at8_compression_introducing_non_compressible_violation_fails_after_revalidation(
    registry: LayoutConstraintRegistry,
) -> None:
    def drop_phase_during_compression(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        updated = _shorten_to_limits(slide_spec, violations)
        updated["phases"] = updated["phases"][:1]
        return updated

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 29, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=drop_phase_during_compression,
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 1
    assert result.slide_spec is None
    assert result.error_code == CONTENT_CONSTRAINT_EXCEEDED
    assert "below minimum" in (result.message or "")


def test_at8_noop_compress_invoked_exactly_twice_before_failure(registry: LayoutConstraintRegistry) -> None:
    calls = {"compress": 0}

    def counting_noop(slide_spec: dict, violations: list[ConstraintViolation]) -> dict:
        calls["compress"] += 1
        return copy.deepcopy(slide_spec)

    slide_spec = {
        "layoutId": "TIMELINE_01",
        "sourceChapterIds": ["10"],
        "title": "Timeline",
        "phases": [
            {"name": "A" * 40, "description": "ok"},
            {"name": "Phase B", "description": "ok"},
        ],
    }
    result = validate_and_compress_slide_spec(
        slide_spec,
        registry=registry,
        compress=counting_noop,
    )
    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == MAX_COMPRESSION_ATTEMPTS
    assert calls["compress"] == MAX_COMPRESSION_ATTEMPTS


def test_at8_path_helpers_round_trip_nested_fields() -> None:
    payload = {
        "phases": [
            {"name": "Alpha", "description": "First phase"},
            {"name": "Beta"},
        ],
        "meta": {"note": "ok"},
    }
    assert get_value_at_path(payload, "phases[0].name") == "Alpha"
    assert get_value_at_path(payload, "meta.note") == "ok"
    set_value_at_path(payload, "phases[1].name", "Gamma")
    assert payload["phases"][1]["name"] == "Gamma"
