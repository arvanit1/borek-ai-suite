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
from services.validation.source_chapter_enforcement import (
    SourceChapterEnforcementError,
    validate_field_provenance,
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


def _chapter_only_provenance(spec: dict[str, Any], chapter_id: str) -> None:
    spec["sourceChapterIds"] = [chapter_id]
    spec["fieldProvenance"] = [
        {**entry, "sourceChapterIds": [chapter_id]}
        for entry in spec["fieldProvenance"]
        if isinstance(entry, dict) and entry.get("path") != "subtitle"
    ]


def _validate_bt14(spec: dict[str, Any]) -> None:
    validate_field_provenance(
        spec,
        real_chapter_ids=("1", "2"),
        allowed_chapter_ids=("1", "2"),
    )


def test_repair_empty_subtitle_uses_grounded_chapter_title() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    spec["subtitle"] = ""
    _chapter_only_provenance(spec, "2")
    before = copy.deepcopy(spec)

    repaired = repair_empty_subtitle(spec, _chapters())

    assert before["sourceChapterIds"] == ["2"]
    assert "subtitle" not in before or before.get("subtitle") == ""
    assert not any(
        entry.get("path") == "subtitle"
        for entry in before["fieldProvenance"]
        if isinstance(entry, dict)
    )

    assert repaired["subtitle"] == "Management summary"
    subtitle_provenance = [
        entry
        for entry in repaired["fieldProvenance"]
        if isinstance(entry, dict) and entry.get("path") == "subtitle"
    ]
    assert len(subtitle_provenance) == 1
    assert subtitle_provenance[0]["sourceChapterIds"] == ["1"]
    assert repaired["sourceChapterIds"] == ["2", "1"]
    _validate_bt14(repaired)


def test_repair_whitespace_subtitle_is_not_left_in_place() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    spec["subtitle"] = "   "
    repaired = repair_empty_subtitle(spec, _chapters())
    assert repaired.get("subtitle") != "   "
    assert isinstance(repaired.get("subtitle"), str)
    assert repaired["subtitle"].strip()


def test_valid_subtitle_is_unchanged() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    before = copy.deepcopy(spec)
    repaired = repair_empty_subtitle(spec, _chapters())
    assert repaired == before


def test_repair_empty_subtitle_resyncs_root_for_executive_summary() -> None:
    spec = _load_json(EXEC_FIXTURE)
    spec["subtitle"] = ""
    _chapter_only_provenance(spec, "2")

    repaired = repair_empty_subtitle(spec, _chapters())

    assert repaired["subtitle"] == "Management summary"
    assert repaired["sourceChapterIds"] == ["2", "1"]
    _validate_bt14(repaired)


def test_blank_subtitle_omitted_resyncs_root_union() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    spec["subtitle"] = ""
    _chapter_only_provenance(spec, "2")
    spec["sourceChapterIds"] = ["1", "2"]
    chapters = (
        {
            "chapter_id": "2",
            "title": "",
            "body": "",
        },
    )

    repaired = repair_empty_subtitle(spec, chapters)

    assert "subtitle" not in repaired
    assert repaired["sourceChapterIds"] == ["2"]
    _validate_bt14(repaired)


def test_multiple_fields_preserve_exact_bt14_union() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    spec["subtitle"] = ""
    spec["sourceChapterIds"] = ["2"]
    spec["fieldProvenance"] = [
        {"path": "sectionLabel", "sourceChapterIds": ["1", "2"]},
        {"path": "title", "sourceChapterIds": ["2"]},
        {"path": "problem.title", "sourceChapterIds": ["2"]},
        {"path": "problem.description", "sourceChapterIds": ["2"]},
        {"path": "solution.title", "sourceChapterIds": ["1"]},
        {"path": "solution.description", "sourceChapterIds": ["1"]},
        {"path": "currentState.title", "sourceChapterIds": ["2"]},
        {"path": "currentState.description", "sourceChapterIds": ["2"]},
        {"path": "targetState.title", "sourceChapterIds": ["1"]},
        {"path": "targetState.description", "sourceChapterIds": ["1"]},
    ]

    repaired = repair_empty_subtitle(spec, _chapters())

    assert repaired["sourceChapterIds"] == ["1", "2"]
    _validate_bt14(repaired)


def test_unsynchronized_fixture_still_fails_without_repair() -> None:
    spec = _load_json(CONTEXT_FIXTURE)
    spec["subtitle"] = "Management summary"
    spec["sourceChapterIds"] = ["2"]
    spec["fieldProvenance"] = [
        entry
        for entry in spec["fieldProvenance"]
        if isinstance(entry, dict) and entry.get("path") != "subtitle"
    ]
    spec["fieldProvenance"].append(
        {"path": "subtitle", "sourceChapterIds": ["1"]}
    )

    with pytest.raises(SourceChapterEnforcementError, match="absent from root"):
        _validate_bt14(spec)


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
