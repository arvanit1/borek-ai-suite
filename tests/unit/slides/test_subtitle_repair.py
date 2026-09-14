"""Regression tests for empty optional subtitle repair."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from services.slides.content_generation.group_a.common import (
    SlideSpecValidationError,
    StructuredGenerationRequest,
)
from services.slides.content_generation.group_a.context_01 import generate_context_01
from services.slides.content_generation.group_a.subtitle_repair import (
    format_empty_subtitle_retry_message,
    repair_empty_subtitle,
)
from services.slides.content_generation.summary.executive_summary_01 import (
    generate_executive_summary_01,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
CONTEXT_FIXTURE = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a" / "context_01.realistic.json"
)
EXEC_FIXTURE = (
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
    requests: list[StructuredGenerationRequest] = field(default_factory=list)

    def __call__(self, request: StructuredGenerationRequest) -> dict[str, Any]:
        self.requests.append(request)
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


def _chapters() -> tuple[dict[str, Any], ...]:
    framework = _framework()
    by_id = {chapter["chapter_id"]: chapter for chapter in framework["chapters"]}
    return tuple(
        {
            "chapter_id": chapter_id,
            "title": by_id[chapter_id]["title"],
            "body": copy.deepcopy(by_id[chapter_id]["body"]),
        }
        for chapter_id in ("1", "2")
    )


def _no_op_compressor(values: dict[str, str], _violations: list[Any]) -> dict[str, str]:
    return values


def test_repair_empty_subtitle_uses_grounded_chapter_title() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    spec["subtitle"] = ""
    repaired = repair_empty_subtitle(spec, _chapters())
    assert repaired["subtitle"] == "Management summary"
    subtitle_provenance = [
        entry
        for entry in repaired["fieldProvenance"]
        if isinstance(entry, dict) and entry.get("path") == "subtitle"
    ]
    assert len(subtitle_provenance) == 1
    assert subtitle_provenance[0]["sourceChapterIds"] == ["1"]


def test_repair_whitespace_subtitle_is_not_left_in_place() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    spec["subtitle"] = "   "
    repaired = repair_empty_subtitle(spec, _chapters())
    assert repaired.get("subtitle") != "   "
    assert isinstance(repaired.get("subtitle"), str)
    assert repaired["subtitle"].strip()


def test_valid_subtitle_is_unchanged() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    repaired = repair_empty_subtitle(spec, _chapters())
    assert repaired["subtitle"] == spec["subtitle"]


def test_context_01_empty_subtitle_from_llm_is_accepted() -> None:
    invalid = _load_json(CONTEXT_FIXTURE)
    invalid["subtitle"] = ""
    result = generate_context_01(
        _framework(),
        structured_generate=CapturingGenerator(output=invalid),
        compress_fields=_no_op_compressor,
    )
    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["subtitle"] == "Management summary"


def test_executive_summary_01_empty_subtitle_from_llm_is_accepted() -> None:
    invalid = _load_json(EXEC_FIXTURE)
    invalid["subtitle"] = ""
    result = generate_executive_summary_01(
        _framework(),
        structured_generate=CapturingGenerator(output=invalid),
        compress_fields=_no_op_compressor,
    )
    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["subtitle"] == "Management summary"


def test_empty_subtitle_retry_message_names_field() -> None:
    message = "Invalid CONTEXT_01 SlideSpec at $.subtitle: '' should be non-empty"
    retry = format_empty_subtitle_retry_message(message)
    assert "empty subtitle" in retry
    assert "omit subtitle" in retry


def test_context_01_retries_when_repair_disabled_and_subtitle_stays_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from services.slides.content_generation.group_a import context_01

    monkeypatch.setattr(
        context_01,
        "CONFIG",
        replace(context_01.CONFIG, pre_validate_repair=None),
    )

    invalid = _load_json(CONTEXT_FIXTURE)
    invalid["subtitle"] = ""
    accepted = _load_json(CONTEXT_FIXTURE)
    generator = SequentialGenerator(outputs=[invalid, accepted])

    result = generate_context_01(
        _framework(),
        structured_generate=generator,
        compress_fields=_no_op_compressor,
    )

    assert result.status == "VALID"
    assert len(generator.requests) == 2
    assert "empty subtitle" in generator.requests[1].instructions


def test_repeated_empty_subtitle_fails_closed_after_bounded_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from services.slides.content_generation.group_a import context_01

    monkeypatch.setattr(
        context_01,
        "CONFIG",
        replace(context_01.CONFIG, pre_validate_repair=None),
    )

    invalid = _load_json(CONTEXT_FIXTURE)
    invalid["subtitle"] = ""
    generator = SequentialGenerator(outputs=[invalid, invalid, invalid])

    with pytest.raises(SlideSpecValidationError, match="subtitle"):
        generate_context_01(
            _framework(),
            structured_generate=generator,
            compress_fields=_no_op_compressor,
        )

    assert len(generator.requests) == 3
