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
from services.slides.content_generation.group_a.cover_01 import (
    MAX_STAT_BADGES,
    generate_cover_01,
)
from services.slides.content_generation.group_a.problem_solution_01 import (
    generate_problem_solution_01,
)
from services.slides.content_generation.group_a.requirements_matrix_01 import (
    generate_requirements_matrix_01,
)
from services.slides.content_generation.group_a.scope_01 import generate_scope_01
from services.validation.source_chapter_enforcement import validate_field_provenance

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
    assert "fieldProvenance" in request.target_schema["properties"]
    assert "exactly one provenance entry" in request.instructions
    assert "do not copy the full root list onto every field" in request.instructions
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
def test_bt14_generated_group_a_output_requires_field_provenance(case: Case) -> None:
    invalid = _slide(case)
    del invalid["fieldProvenance"]

    with pytest.raises(SourceChapterValidationError, match="fieldProvenance"):
        _run(case, _framework(), CapturingGenerator(output=invalid))


def test_bt14_generated_output_rejects_missing_nested_field_attribution() -> None:
    case = CASES["context"]
    invalid = _slide(case)
    invalid["fieldProvenance"] = [
        entry
        for entry in invalid["fieldProvenance"]
        if entry["path"] != "problem.description"
    ]

    with pytest.raises(SourceChapterValidationError, match="problem.description"):
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
        invalid["fieldProvenance"].extend(
            [
                {"path": "statBadges[3].value", "sourceChapterIds": ["1"]},
                {"path": "statBadges[3].label", "sourceChapterIds": ["1"]},
            ]
        )
    elif case.layout_id == "SCOPE_01":
        invalid["included"] = ["Included item" for _ in range(8)]
        invalid["fieldProvenance"].extend(
            {
                "path": f"included[{index}]",
                "sourceChapterIds": ["3"],
            }
            for index in range(5, 8)
        )
    elif case.layout_id == "REQUIREMENTS_MATRIX_01":
        invalid["requirements"] = invalid["requirements"] + [
            {"category": "G", "title": "Extra requirement", "status": "later"}
        ]
        invalid["fieldProvenance"].extend(
            {
                "path": f"requirements[6].{field_name}",
                "sourceChapterIds": ["5"],
            }
            for field_name in ("category", "title", "status")
        )
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


def test_bt14_numeric_grounding_uses_the_fields_attributed_chapters() -> None:
    case = CASES["context"]
    context = _slide(case)
    context["problem"]["description"] = "The target automation rate is 80%."

    with pytest.raises(UngroundedContentError, match="problem.description"):
        _run(case, _framework(), CapturingGenerator(output=context))

    problem_provenance = next(
        entry
        for entry in context["fieldProvenance"]
        if entry["path"] == "problem.description"
    )
    problem_provenance["sourceChapterIds"] = ["1"]
    result = _run(case, _framework(), CapturingGenerator(output=context))
    assert result.status == "VALID"


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


class _ContextSpec(dict):
    """CONTEXT_01 SlideSpec plus the FrameworkObject used to validate it."""

    framework: dict[str, Any]


def build_context_01_spec(
    *,
    problem_description: str,
    problem_provenance: list[str],
    chapter_bodies: dict[str, str],
) -> _ContextSpec:
    framework = _framework()
    for chapter in framework["chapters"]:
        chapter_id = str(chapter.get("chapter_id"))
        if chapter_id in chapter_bodies:
            chapter["body"] = chapter_bodies[chapter_id]
    spec = _ContextSpec(_slide(CASES["context"]))
    spec.framework = framework
    spec["problem"] = {
        **copy.deepcopy(spec["problem"]),
        "description": problem_description,
    }
    spec["solution"] = {
        **copy.deepcopy(spec["solution"]),
        "description": (
            "A deterministic three-way match handles clean invoices "
            "and explains every exception."
        ),
    }
    spec["fieldProvenance"] = [
        {
            **copy.deepcopy(entry),
            "sourceChapterIds": list(problem_provenance),
        }
        if entry["path"] == "problem.description"
        else copy.deepcopy(entry)
        for entry in spec["fieldProvenance"]
    ]
    return spec


def validate_group_a_content(spec: dict[str, Any]) -> Any:
    framework = getattr(spec, "framework", None)
    if not isinstance(framework, dict):
        raise TypeError("build_context_01_spec must be used to construct the spec")
    return _run(
        CASES["context"],
        framework,
        CapturingGenerator(output=dict(spec)),
    )


def test_bt14_digit_form_of_word_concept_fails_grounding() -> None:
    """
    BT-14: model writes "3-way match" (digit) but chapter
    body contains only "three-way-match" (word form).
    The digit 3 is ungrounded — must fail.
    This is the exact live failure for opportunity
    aff77ed5 CONTEXT_01 problem.description.
    """
    spec = build_context_01_spec(
        problem_description=(
            "Invoices require a 3-way match process "
            "before payment is approved."
        ),
        problem_provenance=["2"],
        chapter_bodies={
            "1": "Management handles approval workflows.",
            "2": (
                "The process involves three-way-match "
                "validation and approval steps."
            ),
        },
    )
    with pytest.raises(UngroundedContentError) as exc_info:
        validate_group_a_content(spec)
    assert "3" in str(exc_info.value)
    assert "problem.description" in str(exc_info.value)


def test_bt14_word_form_of_numeric_concept_passes_grounding() -> None:
    """
    BT-14: model writes "three-way match" (word form).
    No digit token is extracted. Must pass.
    This is what Fix 1 and Fix 3 produce.
    """
    spec = build_context_01_spec(
        problem_description=(
            "Invoices require a three-way match process "
            "before payment is approved."
        ),
        problem_provenance=["2"],
        chapter_bodies={
            "1": "Management handles approval workflows.",
            "2": (
                "The process involves three-way-match "
                "validation and approval steps."
            ),
        },
    )
    result = validate_group_a_content(spec)
    assert result.status == "VALID"


def test_sanitizer_converts_3way_to_three_way() -> None:
    """
    Fix 3 sanitizer: "3-way match" → "three-way match"
    when "3" is not in any allowed chapter body.
    """
    from llm.live_slide_repair import _sanitize_ungrounded_digit_compounds

    result = _sanitize_ungrounded_digit_compounds(
        text="Invoices require a 3-way match process.",
        allowed_chapter_bodies={
            "1": "Management handles approval workflows.",
            "2": "The process involves three-way-match validation.",
        },
        ungrounded_tokens={"3"},
    )
    assert "3-way" not in result
    assert "three-way" in result


def test_compression_restores_european_thousand_form() -> None:
    """AT-8 must not turn a grounded 1.200 into an ungrounded 1200."""
    from llm.client import _restore_source_number_forms

    result = _restore_source_number_forms(
        "Around 1.200 invoices arrive each month.",
        "Around 1200 invoices arrive each month.",
    )
    assert "1.200" in result
    assert "1200" not in result


def test_sanitizer_leaves_grounded_digits_alone() -> None:
    """
    Fix 3 sanitizer: if "5" appears as a digit in the
    chapter body, it is grounded and must not be changed.
    """
    from llm.live_slide_repair import _sanitize_ungrounded_digit_compounds

    result = _sanitize_ungrounded_digit_compounds(
        text="Processing 5 invoices per day.",
        allowed_chapter_bodies={
            "2": "The team processes 5 invoices per day on average."
        },
        ungrounded_tokens=set(),
    )
    assert "5" in result
    assert "five" not in result


class _ScopeSpec(dict):
    framework: dict[str, Any]


def build_scope_01_spec(
    *,
    included_1: str,
    chapter_bodies: dict[str, str],
) -> _ScopeSpec:
    framework = _framework()
    for chapter in framework["chapters"]:
        chapter_id = str(chapter.get("chapter_id"))
        if chapter_id in chapter_bodies:
            chapter["body"] = chapter_bodies[chapter_id]
    spec = _ScopeSpec(_slide(CASES["scope"]))
    spec.framework = framework
    included = list(spec["included"])
    included[1] = included_1
    spec["included"] = included
    return spec


def validate_group_a_scope(spec: dict[str, Any]) -> Any:
    framework = getattr(spec, "framework", None)
    if not isinstance(framework, dict):
        raise TypeError("build_scope_01_spec must be used to construct the spec")
    return _run(
        CASES["scope"],
        framework,
        CapturingGenerator(output=dict(spec)),
    )


def test_bt14_scope_rejects_ungrounded_70() -> None:
    spec = build_scope_01_spec(
        included_1="Handles 70% of cases",
        chapter_bodies={
            "3": "handles seventy percent of cases",
            "5": "reduces manual effort significantly",
        },
    )
    with pytest.raises(UngroundedContentError) as exc_info:
        validate_group_a_scope(spec)
    assert "70" in str(exc_info.value)
    assert "included[1]" in str(exc_info.value)


def test_bt14_scope_accepts_word_form_seventy() -> None:
    spec = build_scope_01_spec(
        included_1="Handles seventy percent of cases",
        chapter_bodies={
            "3": "handles seventy percent of cases",
            "5": "reduces manual effort significantly",
        },
    )
    result = validate_group_a_scope(spec)
    assert result.status == "VALID"


def test_sanitizer_converts_70_percent_to_seventy_percent() -> None:
    from llm.live_slide_repair import _sanitize_ungrounded_digit_compounds

    result = _sanitize_ungrounded_digit_compounds(
        text="Handles 70% of cases",
        allowed_chapter_bodies={
            "3": "handles seventy percent of cases",
            "5": "reduces manual effort significantly",
        },
        ungrounded_tokens={"70"},
    )
    assert "70%" not in result
    assert "seventy percent" in result


def test_sanitizer_spells_ungrounded_250() -> None:
    from llm.live_slide_repair import _sanitize_ungrounded_digit_compounds

    result = _sanitize_ungrounded_digit_compounds(
        text="Around 250 invoices need review.",
        allowed_chapter_bodies={"2": "Invoices need review each month."},
        ungrounded_tokens={"250"},
    )
    assert "250" not in result
    assert "two hundred fifty" in result


def _overflow_cover(extra_count: int) -> dict[str, Any]:
    cover = _slide(CASES["cover"])
    extras = [
        {"value": "12 weeks", "label": "Delivery duration"},
        {"value": "4", "label": "Team size"},
        {"value": "85%", "label": "Automation rate"},
    ]
    for index in range(extra_count):
        badge = extras[index % len(extras)]
        cover["statBadges"].append(
            {"value": badge["value"], "label": f"Additional {badge['label']}"}
        )
        offset = 3 + index
        cover["fieldProvenance"].extend(
            [
                {"path": f"statBadges[{offset}].value", "sourceChapterIds": ["1"]},
                {"path": f"statBadges[{offset}].label", "sourceChapterIds": ["1"]},
            ]
        )
    return cover


def test_cover_prompt_states_maximum_three_stat_badges() -> None:
    generator = CapturingGenerator(output=_slide(CASES["cover"]))

    _run(CASES["cover"], _framework(), generator)

    instructions = generator.requests[0].instructions
    assert "at most 3 statBadges" in instructions
    assert "strongest grounded quantitative facts" in instructions
    assert "Do not invent metrics" in instructions


def test_cover_one_stat_badge_is_unchanged() -> None:
    cover = _slide(CASES["cover"])
    cover["statBadges"] = cover["statBadges"][:1]
    cover["fieldProvenance"] = [
        entry
        for entry in cover["fieldProvenance"]
        if not str(entry["path"]).startswith("statBadges[") or entry["path"].startswith("statBadges[0]")
    ]

    result = _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["statBadges"] == cover["statBadges"]
    assert result.slide_spec["fieldProvenance"] == cover["fieldProvenance"]


def test_cover_three_stat_badges_are_unchanged() -> None:
    cover = _slide(CASES["cover"])

    result = _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["statBadges"] == cover["statBadges"]
    assert len(result.slide_spec["statBadges"]) == MAX_STAT_BADGES


@pytest.mark.parametrize("extra_count", [1, 2])
def test_cover_generation_rejects_overflow_without_mutating_payload(extra_count: int) -> None:
    overflow = _overflow_cover(extra_count)
    original = copy.deepcopy(overflow)
    generator = CapturingGenerator(output=overflow)

    result = _run(CASES["cover"], _framework(), generator)

    assert result.status == "VALIDATION_FAILED"
    assert result.slide_spec is None
    assert result.compression_attempts == 0
    assert generator.output == original


def test_cover_zero_stat_badges_still_fail_bt15_min_items() -> None:
    cover = _slide(CASES["cover"])
    cover["statBadges"] = []
    cover["fieldProvenance"] = [
        entry
        for entry in cover["fieldProvenance"]
        if not str(entry["path"]).startswith("statBadges[")
    ]

    result = _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))

    assert result.status == "VALIDATION_FAILED"
    assert result.slide_spec is None


def test_other_group_a_layouts_do_not_trim_overflow_arrays() -> None:
    case = CASES["scope"]
    invalid = _slide(case)
    invalid["included"] = ["Included item" for _ in range(8)]
    invalid["fieldProvenance"].extend(
        {"path": f"included[{index}]", "sourceChapterIds": ["3"]}
        for index in range(5, 8)
    )

    result = _run(case, _framework(), CapturingGenerator(output=invalid))

    assert result.status == "VALIDATION_FAILED"
    assert result.slide_spec is None
