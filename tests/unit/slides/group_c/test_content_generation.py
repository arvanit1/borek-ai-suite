"""MS-6..MS-10 Group C content-generation behavior and boundary tests."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import jsonschema
import pytest

from services.slides.content_generation.group_c.architecture_01 import (
    generate_architecture_01,
)
from services.slides.content_generation.group_c.common import (
    FrameworkNotConfirmedError,
    GroupCBusinessValidationError,
    ProhibitedCommercialContentError,
    SlideSpecValidationError,
    SourceChapterValidationError,
    StructuredGenerationFailure,
    StructuredGenerationRequest,
    UngroundedContentError,
)
from services.slides.content_generation.group_c.compliance_01 import generate_compliance_01
from services.slides.content_generation.group_c.next_steps_01 import generate_next_steps_01
from services.slides.content_generation.group_c.open_questions_01 import (
    generate_open_questions_01,
)
from services.slides.content_generation.group_c.success_metrics_01 import (
    generate_success_metrics_01,
)

ROOT = Path(__file__).resolve().parents[4]
FRAMEWORK_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_c.json"
FRAMEWORK_SCHEMA_PATH = ROOT / "packages" / "contracts" / "framework_object.schema.json"
SLIDE_FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec"

GeneratorEntryPoint = Callable[..., Any]


@dataclass(frozen=True)
class Case:
    entrypoint: GeneratorEntryPoint
    fixture_name: str
    layout_id: str
    allowed_chapter_ids: tuple[str, ...]
    required_layout_field: str
    missing_nested_path: str


CASES = {
    "architecture": Case(
        generate_architecture_01,
        "architecture_01.minimal.json",
        "ARCHITECTURE_01",
        ("6", "7"),
        "components",
        "components[0].description",
    ),
    "compliance": Case(
        generate_compliance_01,
        "compliance_01.minimal.json",
        "COMPLIANCE_01",
        ("8",),
        "items",
        "items[0].text",
    ),
    "success_metrics": Case(
        generate_success_metrics_01,
        "success_metrics_01.minimal.json",
        "SUCCESS_METRICS_01",
        ("3", "9"),
        "criteria",
        "criteria[0].description",
    ),
    "open_questions": Case(
        generate_open_questions_01,
        "open_questions_01.minimal.json",
        "OPEN_QUESTIONS_01",
        ("11",),
        "left",
        "left.items[0]",
    ),
    "next_steps": Case(
        generate_next_steps_01,
        "next_steps_01.minimal.json",
        "NEXT_STEPS_01",
        ("13",),
        "steps",
        "steps[0].text",
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


def _overflow_for_structural_limits(case: Case) -> dict[str, Any]:
    invalid = _slide(case)
    extras = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")
    if case.layout_id == "ARCHITECTURE_01":
        start = len(invalid["components"])
        invalid["components"] = invalid["components"] + [
            {"number": start + index + 1, "title": f"Extra {label}", "description": "Overflow node"}
            for index, label in enumerate(extras)
        ]
        invalid["fieldProvenance"].extend(
            {
                "path": f"components[{index}].{field_name}",
                "sourceChapterIds": [case.allowed_chapter_ids[0]],
            }
            for index in range(start, start + len(extras))
            for field_name in ("number", "title", "description")
        )
    elif case.layout_id == "COMPLIANCE_01":
        start = len(invalid["items"])
        invalid["items"] = invalid["items"] + [
            {"icon": "note", "text": f"Additional {label} control"}
            for label in extras
        ]
        invalid["fieldProvenance"].extend(
            {
                "path": f"items[{index}].{field_name}",
                "sourceChapterIds": ["8"],
            }
            for index in range(start, start + len(extras))
            for field_name in ("icon", "text")
        )
    elif case.layout_id == "SUCCESS_METRICS_01":
        start = len(invalid["criteria"])
        invalid["criteria"] = invalid["criteria"] + [
            {"title": f"Extra {label}", "description": "Operational handling quality"}
            for label in extras
        ]
        invalid["fieldProvenance"].extend(
            {
                "path": f"criteria[{index}].{field_name}",
                "sourceChapterIds": ["3"],
            }
            for index in range(start, start + len(extras))
            for field_name in ("title", "description")
        )
    elif case.layout_id == "OPEN_QUESTIONS_01":
        start = len(invalid["left"]["items"])
        invalid["left"]["items"] = invalid["left"]["items"] + [
            f"Follow-up {label} still open"
            for label in extras
        ]
        invalid["fieldProvenance"].extend(
            {
                "path": f"left.items[{index}]",
                "sourceChapterIds": ["11"],
            }
            for index in range(start, start + len(extras))
        )
    else:
        start = len(invalid["checklist"])
        invalid["checklist"] = invalid["checklist"] + [
            f"Confirm {label} close-out"
            for label in extras
        ]
        invalid["fieldProvenance"].extend(
            {
                "path": f"checklist[{index}]",
                "sourceChapterIds": ["13"],
            }
            for index in range(start, start + len(extras))
        )
    return invalid


def _plant_commercial_copy(case: Case, prohibited: str) -> dict[str, Any]:
    slide_spec = _slide(case)
    if case.layout_id == "ARCHITECTURE_01":
        slide_spec["subtitle"] = prohibited
    elif case.layout_id == "COMPLIANCE_01":
        slide_spec["items"][0]["text"] = prohibited
    elif case.layout_id == "SUCCESS_METRICS_01":
        slide_spec["criteria"][0]["description"] = prohibited
    elif case.layout_id == "OPEN_QUESTIONS_01":
        slide_spec["left"]["items"][0] = prohibited
    else:
        slide_spec["checklist"][0] = prohibited
    return slide_spec


def test_confirmed_group_c_framework_fixture_matches_canonical_at1_schema() -> None:
    jsonschema.Draft202012Validator(_load_json(FRAMEWORK_SCHEMA_PATH)).validate(_framework())


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_valid_generated_group_c_slide_spec_is_accepted(case: Case) -> None:
    generator = CapturingGenerator(output=_slide(case))

    result = _run(case, _framework(), generator)

    assert result.status == "VALID"
    assert result.compression_attempts == 0
    assert result.slide_spec is not None
    assert result.slide_spec["layoutId"] == case.layout_id
    assert set(result.slide_spec["sourceChapterIds"]).issubset(case.allowed_chapter_ids)
    assert case.required_layout_field in result.slide_spec
    if case.layout_id == "ARCHITECTURE_01":
        assert len(result.slide_spec["components"]) >= 2


@pytest.mark.parametrize("status", ["draft", "in_review"])
@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_group_c_generation_rejects_non_confirmed_framework(
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
    assert "fieldProvenance" in request.target_schema["properties"]
    assert "exactly one provenance entry" in request.instructions
    assert "do not copy the full root list onto every field" in request.instructions
    request_text = json.dumps(request.chapters)
    assert "transcript-group-c-001" not in request_text
    assert "source_refs" not in request_text
    assert "generated_from" not in request_text


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_invalid_schema_output_is_rejected(case: Case) -> None:
    invalid = _slide(case)
    del invalid[case.required_layout_field]

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_ms11_generated_group_c_output_requires_field_provenance(case: Case) -> None:
    invalid = _slide(case)
    del invalid["fieldProvenance"]

    with pytest.raises(SourceChapterValidationError, match="fieldProvenance"):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_ms11_generated_output_rejects_missing_nested_field_attribution(case: Case) -> None:
    invalid = _slide(case)
    invalid["fieldProvenance"] = [
        entry
        for entry in invalid["fieldProvenance"]
        if entry["path"] != case.missing_nested_path
    ]

    with pytest.raises(SourceChapterValidationError, match=re.escape(case.missing_nested_path)):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_wrong_layout_id_is_rejected(case: Case) -> None:
    invalid = _slide(case)
    invalid["layoutId"] = "COVER_01"

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_unsupported_or_invented_source_chapter_is_rejected(case: Case) -> None:
    invalid = _slide(case)
    invalid["sourceChapterIds"] = ["1"]

    with pytest.raises(SourceChapterValidationError):
        _run(case, _framework(), CapturingGenerator(output=invalid))


@pytest.mark.parametrize("case_name", ["architecture", "success_metrics"])
def test_unused_allowed_chapter_is_not_forced_into_source_chapter_ids(case_name: str) -> None:
    case = CASES[case_name]
    slide_spec = _slide(case)
    slide_spec["sourceChapterIds"] = [case.allowed_chapter_ids[0]]
    for entry in slide_spec["fieldProvenance"]:
        entry["sourceChapterIds"] = [case.allowed_chapter_ids[0]]

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


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_duplicate_source_chapter_ids_are_rejected(case: Case) -> None:
    slide_spec = _slide(case)
    first = case.allowed_chapter_ids[0]
    slide_spec["sourceChapterIds"] = [first, first]

    with pytest.raises(SlideSpecValidationError):
        _run(case, _framework(), CapturingGenerator(output=slide_spec))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_ms12_structural_limits_are_applied_after_generation(case: Case) -> None:
    result = _run(case, _framework(), CapturingGenerator(output=_overflow_for_structural_limits(case)))

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == 0


def test_ms15_compression_path_is_reachable_for_excessive_generated_text() -> None:
    case = CASES["architecture"]
    overlong = _slide(case)
    overlong["components"][0]["description"] = "D" * 101
    compressor_calls: list[dict[str, str]] = []

    def compress(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
        compressor_calls.append(copy.deepcopy(values))
        return {"components[0].description": "Source of invoices, read-only"}

    result = _run(
        case,
        _framework(),
        CapturingGenerator(output=overlong),
        compressor=compress,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert compressor_calls == [{"components[0].description": "D" * 101}]


def test_structured_generator_failure_is_surfaced_cleanly() -> None:
    case = CASES["compliance"]

    with pytest.raises(StructuredGenerationFailure, match="COMPLIANCE_01"):
        _run(
            case,
            _framework(),
            CapturingGenerator(error=RuntimeError("provider unavailable")),
        )


def test_generated_number_absent_from_allowed_chapters_is_rejected() -> None:
    case = CASES["architecture"]
    architecture = _slide(case)
    architecture["components"][0]["description"] = "Handles 99 invoices"

    with pytest.raises(UngroundedContentError, match="99"):
        _run(case, _framework(), CapturingGenerator(output=architecture))


def test_ms13_fewer_than_two_components_fails_before_compression() -> None:
    case = CASES["architecture"]
    invalid = _slide(case)
    invalid["components"] = invalid["components"][:1]
    invalid["fieldProvenance"] = [
        entry
        for entry in invalid["fieldProvenance"]
        if not entry["path"].startswith("components[")
        or entry["path"].startswith("components[0].")
    ]
    invalid["sourceChapterIds"] = ["6"]
    for entry in invalid["fieldProvenance"]:
        entry["sourceChapterIds"] = ["6"]
    calls = {"compress": 0}

    def compress(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
        calls["compress"] += 1
        return values

    with pytest.raises(GroupCBusinessValidationError, match="at least 2 components"):
        _run(
            case,
            _framework(),
            CapturingGenerator(output=invalid),
            compressor=compress,
        )

    assert calls["compress"] == 0


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
@pytest.mark.parametrize(
    "prohibited",
    [
        "€100",
        "EUR 100",
        "ROI 25%",
        "Investment case",
        "Annual cost savings of 20%",
    ],
)
def test_generated_commercial_output_is_rejected_for_every_layout(
    case: Case, prohibited: str
) -> None:
    with pytest.raises(ProhibitedCommercialContentError):
        _run(case, _framework(), CapturingGenerator(output=_plant_commercial_copy(case, prohibited)))


def test_ms6_removes_commercial_framework_content_before_generation() -> None:
    case = CASES["architecture"]
    generator = CapturingGenerator(output=_slide(case))

    _run(case, _framework(), generator)

    chapter_text = json.dumps(generator.requests[0].chapters)
    for prohibited in ("EUR", "investment", "5,000"):
        assert prohibited.casefold() not in chapter_text.casefold()
    assert "AP Mailbox" in chapter_text
    assert "Framework Engine" in chapter_text
    assert "Approval App" in chapter_text
    assert '"investment"' not in chapter_text


def test_ms7_strips_chapter_8_currency_before_generation() -> None:
    case = CASES["compliance"]
    generator = CapturingGenerator(output=_slide(case))

    _run(case, _framework(), generator)

    chapter_text = json.dumps(generator.requests[0].chapters)
    assert "EUR" not in chapter_text
    assert "5,000" not in chapter_text
    assert "least-privilege" in chapter_text
    assert "EU only" in chapter_text


def test_ms8_strips_chapter_9_money_before_generation() -> None:
    case = CASES["success_metrics"]
    generator = CapturingGenerator(output=_slide(case))

    _run(case, _framework(), generator)

    bodies = json.dumps([chapter["body"] for chapter in generator.requests[0].chapters])
    for prohibited in ("EUR", "investment", "payback", "2,400", "476"):
        assert prohibited.casefold() not in bodies.casefold()
    assert "Auto-match rate" in bodies
    assert "85%" in bodies
    assert generator.requests[0].chapters[1]["title"] == "Business case & ROI"


def test_ms8_grounded_non_monetary_metric_is_accepted() -> None:
    case = CASES["success_metrics"]
    metrics = _slide(case)
    metrics["criteria"][0]["description"] = "Target auto-match rate is 85%."
    metrics["fieldProvenance"] = [
        {**entry, "sourceChapterIds": ["3"]}
        if entry["path"].startswith("criteria[0].")
        else entry
        for entry in metrics["fieldProvenance"]
    ]

    result = _run(case, _framework(), CapturingGenerator(output=metrics))

    assert result.status == "VALID"


def test_ms8_numeric_metric_must_come_from_the_attributed_chapter() -> None:
    case = CASES["success_metrics"]
    metrics = _slide(case)
    metrics["criteria"][1]["description"] = "Target auto-match rate is 85%."

    with pytest.raises(UngroundedContentError, match="criteria\\[1\\].description"):
        _run(case, _framework(), CapturingGenerator(output=metrics))


def test_ms8_ms14_currency_on_success_metrics_is_rejected() -> None:
    case = CASES["success_metrics"]
    invalid = _slide(case)
    invalid["criteria"][0]["description"] = "Save EUR 2,400 per month"

    with pytest.raises((ProhibitedCommercialContentError, GroupCBusinessValidationError)):
        _run(case, _framework(), CapturingGenerator(output=invalid))


def test_ms6_compression_cannot_introduce_commercial_content() -> None:
    case = CASES["architecture"]
    architecture = _slide(case)
    architecture["title"] = "T" * 73

    def compress(values: dict[str, str], violations: list[Any]) -> dict[str, str]:
        return {"title": "EUR 100 investment"}

    with pytest.raises(ProhibitedCommercialContentError):
        _run(
            case,
            _framework(),
            CapturingGenerator(output=architecture),
            compressor=compress,
        )


def test_non_monetary_business_language_remains_allowed() -> None:
    case = CASES["architecture"]
    slide_spec = _slide(case)
    slide_spec["components"][0]["description"] = "Source of invoices, read-only"

    result = _run(case, _framework(), CapturingGenerator(output=slide_spec))

    assert result.status == "VALID"
