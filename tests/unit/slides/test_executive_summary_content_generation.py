"""JJ-23: EXECUTIVE_SUMMARY_01 content-generation behavior tests."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from services.slides.content_generation.group_a.common import (
    FrameworkNotConfirmedError,
    SlideSpecValidationError,
    StructuredGenerationRequest,
)
from services.slides.content_generation.summary.executive_summary_01 import (
    generate_executive_summary_01,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
SLIDE_FIXTURE = (
    ROOT
    / "packages"
    / "contracts"
    / "fixtures"
    / "slide_spec"
    / "summary"
    / "executive_summary_01.realistic.json"
)


@dataclass
class CapturingGenerator:
    output: dict[str, Any] | None = None
    error: Exception | None = None
    requests: list[StructuredGenerationRequest] = field(default_factory=list)

    def __call__(self, request: StructuredGenerationRequest) -> dict[str, Any]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.output is not None
        return copy.deepcopy(self.output)


@dataclass
class SequentialGenerator:
    outputs: list[dict[str, Any]]
    requests: list[StructuredGenerationRequest] = field(default_factory=list)

    def __call__(self, request: StructuredGenerationRequest) -> dict[str, Any]:
        self.requests.append(request)
        return copy.deepcopy(self.outputs[len(self.requests) - 1])


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _framework() -> dict[str, Any]:
    return _load_json(FRAMEWORK_FIXTURE_PATH)


def _slide() -> dict[str, Any]:
    return _load_json(SLIDE_FIXTURE)


def _no_op_compressor(values: dict[str, str], _violations: list[Any]) -> dict[str, str]:
    return values


def test_valid_generated_executive_summary_is_accepted() -> None:
    generator = CapturingGenerator(output=_slide())
    result = generate_executive_summary_01(
        _framework(),
        structured_generate=generator,
        compress_fields=_no_op_compressor,
    )
    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["layoutId"] == "EXECUTIVE_SUMMARY_01"
    assert result.slide_spec["sourceChapterIds"] == ["1"]
    assert generator.requests[0].layout_id == "EXECUTIVE_SUMMARY_01"
    assert tuple(chapter["chapter_id"] for chapter in generator.requests[0].chapters) == ("1",)
    assert "at most 32 characters" in generator.requests[0].instructions
    assert "at most 140 characters" in generator.requests[0].instructions


@pytest.mark.parametrize("status", ["draft", "in_review"])
def test_executive_summary_rejects_non_confirmed_framework(status: str) -> None:
    framework_object = _framework()
    framework_object["status"] = status
    with pytest.raises(FrameworkNotConfirmedError):
        generate_executive_summary_01(
            framework_object,
            structured_generate=CapturingGenerator(output=_slide()),
            compress_fields=_no_op_compressor,
        )


def test_invalid_executive_summary_schema_output_is_rejected() -> None:
    invalid = _slide()
    del invalid["headline"]
    with pytest.raises(SlideSpecValidationError):
        generate_executive_summary_01(
            _framework(),
            structured_generate=CapturingGenerator(output=invalid),
            compress_fields=_no_op_compressor,
        )


def test_overflowing_highlight_title_is_regenerated_after_at8_failure() -> None:
    overflowing = _slide()
    overflowing["highlights"][1]["title"] = "Three-way match exception handlings."
    assert len(overflowing["highlights"][1]["title"]) == 36
    accepted = _slide()
    generator = SequentialGenerator(outputs=[overflowing, accepted])

    result = generate_executive_summary_01(
        _framework(),
        structured_generate=generator,
        compress_fields=_no_op_compressor,
    )

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["highlights"][1]["title"] == accepted["highlights"][1]["title"]
    assert len(generator.requests) == 2
    assert "highlights[1].title length 36 exceeds maximum 32" in generator.requests[1].instructions
    assert "Honor every maxLength" in generator.requests[1].instructions


def test_executive_summary_source_chapters_must_stay_in_chapter_1() -> None:
    invalid = _slide()
    invalid["sourceChapterIds"] = ["1", "10"]
    invalid["fieldProvenance"] = [
        {**entry, "sourceChapterIds": ["1", "10"]} for entry in invalid["fieldProvenance"]
    ]
    with pytest.raises(SlideSpecValidationError):
        generate_executive_summary_01(
            _framework(),
            structured_generate=CapturingGenerator(output=invalid),
            compress_fields=_no_op_compressor,
        )
