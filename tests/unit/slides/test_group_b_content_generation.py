"""JJ-5..JJ-9, JJ-11..JJ-13 content-generation behavior and boundary tests."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import jsonschema
import pytest

from services.slides.business_rules import GroupBBusinessRuleError
from services.slides.content_generation.group_b.common import (
    FrameworkNotConfirmedError,
    GroupBBusinessValidationError,
    ProhibitedCommercialContentError,
    SlideSpecValidationError,
    StructuredGenerationFailure,
    StructuredGenerationRequest,
    UngroundedContentError,
)
from services.slides.content_generation.group_b.milestones_01 import generate_milestones_01
from services.slides.content_generation.group_b.process_flow_01 import (
    generate_process_flow_01,
)
from services.slides.content_generation.group_b.team_fte_01 import generate_team_fte_01
from services.slides.content_generation.group_b.timeline_01 import generate_timeline_01
from services.slides.source_chapter_enforcement import SourceChapterValidationError

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_b.json"
FRAMEWORK_SCHEMA_PATH = ROOT / "packages" / "contracts" / "framework_object.schema.json"
SLIDE_FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"

GeneratorEntryPoint = Callable[..., Any]


@dataclass(frozen=True)
class Case:
    entrypoint: GeneratorEntryPoint
    fixture_name: str
    layout_id: str
    allowed_chapter_ids: tuple[str, ...]
    required_layout_field: str


CASES = {
    "process_flow": Case(
        generate_process_flow_01,
        "process_flow_01.realistic.json",
        "PROCESS_FLOW_01",
        ("2", "4"),
        "phases",
    ),
    "timeline": Case(
        generate_timeline_01,
        "timeline_01.realistic.json",
        "TIMELINE_01",
        ("10",),
        "phases",
    ),
    "milestones": Case(
        generate_milestones_01,
        "milestones_01.realistic.json",
        "MILESTONES_01",
        ("10",),
        "milestones",
    ),
    "team_fte": Case(
        generate_team_fte_01,
        "team_fte_01.realistic.json",
        "TEAM_FTE_01",
        ("10",),
        "roles",
    ),
}


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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _framework() -> dict[str, Any]:
    return _load_json(FRAMEWORK_FIXTURE_PATH)


def _slide(case: Case) -> dict[str, Any]:
    return _load_json(SLIDE_FIXTURE_DIR / case.fixture_name)


def _no_op_compressor(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
    return values


def _run(
    case: Case,
    framework_object: dict[str, Any],
    generator: CapturingGenerator,
    *,
    compressor: Callable[[dict[str, str], list[Any]], dict[str, str]] = _no_op_compressor,
):
    return case.entrypoint(
        framework_object,
        structured_generate=generator,
        compress_fields=compressor,
    )


def test_confirmed_group_b_framework_fixture_matches_canonical_at1_schema() -> None:
    jsonschema.Draft202012Validator(_load_json(FRAMEWORK_SCHEMA_PATH)).validate(_framework())


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_valid_generated_group_b_slide_spec_is_accepted(case: Case) -> None:
    generator = CapturingGenerator(output=_slide(case))

    result = _run(case, _framework(), generator)

    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert result.slide_spec is not None
    assert result.slide_spec["layoutId"] == case.layout_id
    assert set(result.slide_spec["sourceChapterIds"]).issubset(case.allowed_chapter_ids)


@pytest.mark.parametrize("status", ["draft", "in_review"])
@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_group_b_generation_rejects_non_confirmed_framework(
    case: Case, status: str
) -> None:
    framework_object = _framework()
    framework_object["status"] = status
    generator = CapturingGenerator(output=_slide(case))

    with pytest.raises(FrameworkNotConfirmedError):
        _run(case, framework_object, generator)

    assert generator.requests == []


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_generator_receives_only_permitted_framework_chapters(case: Case) -> None:
    generator = CapturingGenerator(output=_slide(case))

    _run(case, _framework(), generator)

    request = generator.requests[0]
    assert request.layout_id == case.layout_id
    assert request.target_schema["properties"]["layoutId"]["const"] == case.layout_id
    assert request.instructions
    assert tuple(chapter["chapter_id"] for chapter in request.chapters) == case.allowed_chapter_ids
    assert all(set(chapter) == {"chapter_id", "title", "body"} for chapter in request.chapters)
    request_text = json.dumps(request.chapters)
    assert "transcript-group-b-001" not in request_text
    assert "source_refs" not in request_text
    assert "generated_from" not in request_text


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_invalid_schema_output_is_rejected(case: Case) -> None:
    invalid = _slide(case)
    del invalid[case.required_layout_field]

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_wrong_layout_id_is_rejected(case: Case) -> None:
    invalid = _slide(case)
    invalid["layoutId"] = "ARCHITECTURE_01"

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_jj9_unsupported_or_invented_source_chapter_is_rejected(case: Case) -> None:
    invalid = _slide(case)
    invalid["sourceChapterIds"] = ["13"]

    with pytest.raises(SourceChapterValidationError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


def test_jj9_unused_allowed_chapter_is_not_forced_into_source_chapter_ids() -> None:
    case = CASES["process_flow"]
    slide_spec = _slide(case)
    slide_spec["sourceChapterIds"] = ["2"]

    result = _run(case, _framework(), CapturingGenerator(output=slide_spec))

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["sourceChapterIds"] == ["2"]


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_empty_source_chapter_ids_are_rejected(case: Case) -> None:
    slide_spec = _slide(case)
    slide_spec["sourceChapterIds"] = []

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=slide_spec))


def test_duplicate_source_chapter_ids_are_rejected() -> None:
    case = CASES["process_flow"]
    slide_spec = _slide(case)
    slide_spec["sourceChapterIds"] = ["2", "2"]

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=slide_spec))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_jj10_structural_limits_are_applied_after_generation(case: Case) -> None:
    invalid = _slide(case)
    if case.layout_id == "PROCESS_FLOW_01":
        invalid["phases"] = invalid["phases"] + [
            {"number": 9, "name": "Extra", "description": "Too many phases"}
            for _ in range(4)
        ]
    elif case.layout_id == "TIMELINE_01":
        invalid["phases"] = invalid["phases"] + [
            {"id": f"px{index}", "name": "Extra", "description": "Too many phases"}
            for index in range(5)
        ]
    elif case.layout_id == "MILESTONES_01":
        invalid["milestones"] = invalid["milestones"] + [
            {"name": f"Extra checkpoint {label}", "description": "Too many milestones"}
            for label in ("alpha", "bravo", "charlie", "delta", "echo")
        ]
    else:
        invalid["roles"] = invalid["roles"] + [
            {"role": f"Extra {label}", "fte": "0.3", "responsibility": "Overflow"}
            for label in ("alpha", "bravo", "charlie")
        ]

    result = _run(case, _framework(), CapturingGenerator(output=invalid))

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 0


def test_jj14_compression_path_is_reachable_for_excessive_generated_text() -> None:
    case = CASES["process_flow"]
    overlong = _slide(case)
    overlong["phases"][0]["description"] = "D" * 81
    compressor_calls: list[dict[str, str]] = []

    def compress(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
        compressor_calls.append(copy.deepcopy(values))
        return {"phases[0].description": "Mailbox is the read-only invoice source."}

    result = _run(
        case,
        _framework(),
        CapturingGenerator(output=overlong),
        compressor=compress,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert compressor_calls == [{"phases[0].description": "D" * 81}]


def test_structured_generator_failure_is_surfaced_cleanly() -> None:
    case = CASES["timeline"]

    with pytest.raises(StructuredGenerationFailure, match="TIMELINE_01"):
        _run(
            case,
            _framework(),
            CapturingGenerator(error=RuntimeError("provider unavailable")),
        )


def test_generated_number_absent_from_allowed_chapters_is_rejected() -> None:
    team = _slide(CASES["team_fte"])
    team["roles"][0]["fte"] = "9.9"

    with pytest.raises(UngroundedContentError, match="9.9"):
        _run(CASES["team_fte"], _framework(), CapturingGenerator(output=team))


def test_jj11_invalid_timeline_date_range_fails_before_compression() -> None:
    timeline = _slide(CASES["timeline"])
    timeline["milestones"][0]["date"] = "Week 14"
    timeline["milestones"][-1]["date"] = "Week 2"
    calls = {"compress": 0}

    def compress(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
        calls["compress"] += 1
        return values

    with pytest.raises(GroupBBusinessValidationError, match="end must be on or after"):
        _run(
            CASES["timeline"],
            _framework(),
            CapturingGenerator(output=timeline),
            compressor=compress,
        )

    assert calls["compress"] == 0


def test_jj12_negative_fte_fails_business_validation() -> None:
    team = _slide(CASES["team_fte"])
    team["roles"][0]["fte"] = "-0.3"

    with pytest.raises(GroupBBusinessRuleError, match="must not be negative"):
        _run(CASES["team_fte"], _framework(), CapturingGenerator(output=team))


def test_jj13_duplicate_timeline_milestone_ids_fail_business_validation() -> None:
    timeline = _slide(CASES["timeline"])
    timeline["milestones"][1]["id"] = timeline["milestones"][0]["id"]

    with pytest.raises(GroupBBusinessRuleError, match="must not share an id"):
        _run(CASES["timeline"], _framework(), CapturingGenerator(output=timeline))


def test_jj13_duplicate_standalone_milestone_identities_fail_business_validation() -> None:
    milestones = _slide(CASES["milestones"])
    milestones["milestones"][1]["name"] = milestones["milestones"][0]["name"]

    with pytest.raises(GroupBBusinessRuleError, match="must not share an id"):
        _run(CASES["milestones"], _framework(), CapturingGenerator(output=milestones))


def test_jj8_range_fte_display_is_accepted() -> None:
    team = _slide(CASES["team_fte"])
    team["roles"][0]["fte"] = "0.3-0.5"

    result = _run(CASES["team_fte"], _framework(), CapturingGenerator(output=team))

    assert result.status == "VALID"


def test_commercial_output_is_rejected() -> None:
    process_flow = _slide(CASES["process_flow"])
    process_flow["phases"][0]["description"] = "Investment: EUR 100"

    with pytest.raises(ProhibitedCommercialContentError):
        _run(CASES["process_flow"], _framework(), CapturingGenerator(output=process_flow))
