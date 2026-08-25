"""BT-9..BT-13 content-generation behavior and boundary tests."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import jsonschema
import pytest

from services.slides.content_generation.group_a.common import (
    FrameworkNotConfirmedError,
    ProhibitedCommercialContentError,
    SlideSpecValidationError,
    SourceChapterValidationError,
    StructuredGenerationFailure,
    StructuredGenerationRequest,
    UngroundedContentError,
)
from services.slides.content_generation.group_a.context_01 import generate_context_01
from services.slides.content_generation.group_a.cover_01 import generate_cover_01
from services.slides.content_generation.group_a.problem_solution_01 import (
    generate_problem_solution_01,
)
from services.slides.content_generation.group_a.requirements_matrix_01 import (
    generate_requirements_matrix_01,
)
from services.slides.content_generation.group_a.scope_01 import generate_scope_01

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
FRAMEWORK_SCHEMA_PATH = ROOT / "packages" / "contracts" / "framework_object.schema.json"
SLIDE_FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"

GeneratorEntryPoint = Callable[..., Any]


@dataclass(frozen=True)
class Case:
    entrypoint: GeneratorEntryPoint
    fixture_name: str
    layout_id: str
    allowed_chapter_ids: tuple[str, ...]
    required_layout_field: str


CASES = {
    "cover": Case(
        generate_cover_01,
        "cover_01.realistic.json",
        "COVER_01",
        ("1",),
        "statBadges",
    ),
    "context": Case(
        generate_context_01,
        "context_01.realistic.json",
        "CONTEXT_01",
        ("1", "2"),
        "problem",
    ),
    "problem_solution": Case(
        generate_problem_solution_01,
        "problem_solution_01.realistic.json",
        "PROBLEM_SOLUTION_01",
        ("2", "4"),
        "solution",
    ),
    "scope": Case(
        generate_scope_01,
        "scope_01.realistic.json",
        "SCOPE_01",
        ("3", "5"),
        "included",
    ),
    "requirements": Case(
        generate_requirements_matrix_01,
        "requirements_matrix_01.realistic.json",
        "REQUIREMENTS_MATRIX_01",
        ("5",),
        "requirements",
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


def _no_op_compressor(
    values: dict[str, str], violations: list[Any]
) -> dict[str, str]:
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


def test_confirmed_group_a_framework_fixture_matches_canonical_at1_schema() -> None:
    jsonschema.Draft202012Validator(_load_json(FRAMEWORK_SCHEMA_PATH)).validate(_framework())


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_valid_generated_group_a_slide_spec_is_accepted(case: Case) -> None:
    generator = CapturingGenerator(output=_slide(case))

    result = _run(case, _framework(), generator)

    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert result.slide_spec is not None
    assert result.slide_spec["layoutId"] == case.layout_id
    assert set(result.slide_spec["sourceChapterIds"]).issubset(case.allowed_chapter_ids)


@pytest.mark.parametrize("status", ["draft", "in_review"])
@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_group_a_generation_rejects_non_confirmed_framework(
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
    assert "transcript-group-a-001" not in request_text
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
def test_unsupported_or_invented_source_chapter_is_rejected(case: Case) -> None:
    invalid = _slide(case)
    invalid["sourceChapterIds"] = ["13"]

    with pytest.raises(SourceChapterValidationError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize(
    "case_name",
    ["context", "problem_solution", "scope"],
)
def test_unused_allowed_chapter_is_not_forced_into_source_chapter_ids(
    case_name: str,
) -> None:
    case = CASES[case_name]
    slide_spec = _slide(case)
    slide_spec["sourceChapterIds"] = [case.allowed_chapter_ids[0]]

    result = _run(case, _framework(), CapturingGenerator(output=slide_spec))

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["sourceChapterIds"] == [case.allowed_chapter_ids[0]]


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_empty_source_chapter_ids_are_rejected(case: Case) -> None:
    slide_spec = _slide(case)
    slide_spec["sourceChapterIds"] = []

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=slide_spec))


def test_duplicate_source_chapter_ids_are_rejected() -> None:
    case = CASES["context"]
    slide_spec = _slide(case)
    slide_spec["sourceChapterIds"] = ["1", "1"]

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=slide_spec))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_bt15_structural_limits_are_applied_after_generation(case: Case) -> None:
    invalid = _slide(case)
    if case.layout_id == "COVER_01":
        invalid["statBadges"] = invalid["statBadges"] + [
            {"value": "Extra", "label": "Too many badges"}
        ]
    elif case.layout_id == "SCOPE_01":
        invalid["included"] = ["Included item" for _ in range(8)]
    elif case.layout_id == "REQUIREMENTS_MATRIX_01":
        invalid["requirements"] = invalid["requirements"] + [
            {"category": "G", "title": "Extra requirement", "status": "later"}
        ]
    else:
        invalid["title"] = "T" * 73

    result = _run(case, _framework(), CapturingGenerator(output=invalid))

    assert result.status == "VALIDATION_FAILED"
    expected_attempts = (
        2
        if case.layout_id in {"CONTEXT_01", "PROBLEM_SOLUTION_01"}
        else 0
    )
    assert result.compression_attempts == expected_attempts


def test_bt16_compression_path_is_reachable_for_excessive_generated_text() -> None:
    case = CASES["context"]
    overlong = _slide(case)
    overlong["problem"]["description"] = "P" * 161
    compressor_calls: list[dict[str, str]] = []

    def compress(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
        compressor_calls.append(copy.deepcopy(values))
        return {"problem.description": "Grounded current-state problem."}

    result = _run(
        case,
        _framework(),
        CapturingGenerator(output=overlong),
        compressor=compress,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert compressor_calls == [{"problem.description": "P" * 161}]


def test_structured_generator_failure_is_surfaced_cleanly() -> None:
    case = CASES["scope"]

    with pytest.raises(StructuredGenerationFailure, match="SCOPE_01"):
        _run(
            case,
            _framework(),
            CapturingGenerator(error=RuntimeError("provider unavailable")),
        )


def test_generated_number_absent_from_allowed_chapters_is_rejected() -> None:
    cover = _slide(CASES["cover"])
    cover["statBadges"][0]["value"] = "99%"

    with pytest.raises(UngroundedContentError, match="99"):
        _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))


@pytest.mark.parametrize(
    "prohibited",
    [
        "€100",
        "$100",
        "£100",
        "EUR 100",
        "USD 100",
        "GBP 100",
        "ROI 25%",
        "Payback in 6 months",
        "Investment case",
        "Annual cost savings of 20%",
    ],
)
def test_bt9_rejects_currency_and_commercial_output(prohibited: str) -> None:
    case = CASES["cover"]
    invalid = _slide(case)
    invalid["subtitle"] = prohibited

    with pytest.raises(ProhibitedCommercialContentError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


def test_bt9_removes_commercial_framework_content_before_generation() -> None:
    case = CASES["cover"]
    generator = CapturingGenerator(output=_slide(case))

    _run(case, _framework(), generator)

    chapter_text = json.dumps(generator.requests[0].chapters)
    for prohibited in ("EUR", "investment", "payback", "roi", "cost savings"):
        assert prohibited.casefold() not in chapter_text.casefold()
    assert "80%" in chapter_text
    assert "12 weeks" in chapter_text
    assert "4 people" in chapter_text


def test_bt9_accepts_grounded_non_monetary_metrics() -> None:
    cover = _slide(CASES["cover"])
    cover["statBadges"] = [
        {"value": "80%", "label": "Automation rate"},
        {"value": "12 weeks", "label": "Delivery duration"},
        {"value": "4", "label": "Team size"},
    ]

    result = _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert len(result.slide_spec["statBadges"]) == 3


def test_bt9_compression_cannot_introduce_commercial_content() -> None:
    cover = _slide(CASES["cover"])
    cover["title"] = "T" * 61

    def compress(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
        return {"title": "EUR 100 investment"}

    with pytest.raises(ProhibitedCommercialContentError):
        _run(
            CASES["cover"],
            _framework(),
            CapturingGenerator(output=cover),
            compressor=compress,
        )


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_commercial_output_is_rejected_for_every_group_a_layout(case: Case) -> None:
    slide_spec = _slide(case)
    if case.layout_id == "COVER_01":
        slide_spec["subtitle"] = "Investment: EUR 100"
    elif case.layout_id == "CONTEXT_01":
        slide_spec["problem"]["description"] = "Current cost: EUR 100"
    elif case.layout_id == "PROBLEM_SOLUTION_01":
        slide_spec["solution"]["description"] = "Expected savings: EUR 100"
    elif case.layout_id == "SCOPE_01":
        slide_spec["included"][0] = "Budget approval for EUR 100"
    else:
        slide_spec["requirements"][0]["title"] = "Threshold of EUR 100"

    with pytest.raises(ProhibitedCommercialContentError):
        _run(case, _framework(), CapturingGenerator(output=slide_spec))


@pytest.mark.parametrize(
    ("case_name", "chapter_id"),
    [
        ("context", "2"),
        ("problem_solution", "4"),
        ("scope", "3"),
        ("requirements", "5"),
    ],
)
def test_monetary_framework_content_is_removed_for_bt10_through_bt13(
    case_name: str,
    chapter_id: str,
) -> None:
    case = CASES[case_name]
    framework_object = _framework()
    chapter = next(
        item for item in framework_object["chapters"] if item["chapter_id"] == chapter_id
    )
    chapter["body"].append(
        {
            "amount": "EUR 25,000",
            "requirement": "Values above EUR 25,000 need approval.",
        }
    )
    generator = CapturingGenerator(output=_slide(case))

    _run(case, framework_object, generator)

    request_text = json.dumps(generator.requests[0].chapters)
    assert "EUR" not in request_text
    assert "25,000" not in request_text
    assert '"amount"' not in request_text


def test_chapter_5_monetary_threshold_fixture_cannot_reach_requirements_generator() -> None:
    case = CASES["requirements"]
    generator = CapturingGenerator(output=_slide(case))

    _run(case, _framework(), generator)

    chapter_text = json.dumps(generator.requests[0].chapters)
    assert "EUR" not in chapter_text
    assert "10,000" not in chapter_text
    assert '"amount"' not in chapter_text


def test_non_monetary_business_language_remains_allowed() -> None:
    case = CASES["context"]
    slide_spec = _slide(case)
    slide_spec["problem"]["description"] = "Manual work creates avoidable processing costs."

    result = _run(case, _framework(), CapturingGenerator(output=slide_spec))

    assert result.status == "VALID"


@pytest.mark.parametrize("status", ["included", "partial", "later"])
def test_bt13_accepts_only_canonical_semantic_statuses(status: str) -> None:
    requirements = _slide(CASES["requirements"])
    requirements["requirements"][0]["status"] = status

    result = _run(
        CASES["requirements"],
        _framework(),
        CapturingGenerator(output=requirements),
    )

    assert result.status == "VALID"


def test_bt13_rejects_noncanonical_status() -> None:
    requirements = _slide(CASES["requirements"])
    requirements["requirements"][0]["status"] = "green"

    with pytest.raises(SlideSpecValidationError):
        _run(
            CASES["requirements"],
            _framework(),
            CapturingGenerator(output=requirements),
        )


def test_bt13_rejects_arbitrary_color_or_styling_values() -> None:
    requirements = _slide(CASES["requirements"])
    requirements["requirements"][0]["color"] = "#00FF00"

    with pytest.raises(SlideSpecValidationError):
        _run(
            CASES["requirements"],
            _framework(),
            CapturingGenerator(output=requirements),
        )
