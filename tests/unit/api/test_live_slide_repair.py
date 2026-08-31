"""Live SlideSpec repair for BT-14 provenance gaps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llm.live_slide_repair import repair_live_slide_spec, wrap_live_structured_generator
from services.slides.content_generation.group_a.common import StructuredGenerationRequest
from services.validation.source_chapter_enforcement import validate_field_provenance


def _request(*, chapters: tuple[str, ...], required: list[str] | None = None) -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        layout_id="COVER_01",
        chapters=tuple(
            {"chapter_id": chapter_id, "title": "Context", "body": [{"summary": "80% in 12 weeks"}]}
            for chapter_id in chapters
        ),
        target_schema={
            "type": "object",
            "required": required
            or ["schema_version", "layoutId", "title", "subtitle", "sourceChapterIds", "statBadges"],
        },
        instructions="Generate COVER_01.",
    )


def _cover(*, provenance: list[dict[str, Any]] | None = None, **extra: Any) -> dict[str, Any]:
    spec = {
        "schema_version": "1.0",
        "layoutId": "COVER_01",
        "sectionLabel": "AUTOMATION",
        "title": "Invoice matching",
        "subtitle": "Controlled automation",
        "sourceChapterIds": ["1"],
        "statBadges": [{"value": "80%", "label": "Automation rate"}],
        "fieldProvenance": provenance
        if provenance is not None
        else [
            {"path": "title", "sourceChapterIds": ["1"]},
            {"path": "subtitle", "sourceChapterIds": ["1"]},
            {"path": "statBadges[0].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[0].label", "sourceChapterIds": ["1"]},
        ],
    }
    spec.update(extra)
    return spec


def test_single_chapter_layout_fills_missing_section_label_provenance() -> None:
    spec = _cover()

    repaired = repair_live_slide_spec(spec, _request(chapters=("1",)))

    paths = {entry["path"] for entry in repaired["fieldProvenance"]}
    assert "sectionLabel" in paths
    assert ["1"] == next(
        entry["sourceChapterIds"]
        for entry in repaired["fieldProvenance"]
        if entry["path"] == "sectionLabel"
    )
    assert repaired["sourceChapterIds"] == ["1"]
    assert repaired["sectionLabel"] == "AUTOMATION"


def test_multi_chapter_layout_drops_optional_field_without_guessing() -> None:
    spec = _cover()
    request = _request(chapters=("1", "2"))

    repaired = repair_live_slide_spec(spec, request)

    assert "sectionLabel" not in repaired
    paths = {entry["path"] for entry in repaired["fieldProvenance"]}
    assert "sectionLabel" not in paths


def test_stale_provenance_is_removed() -> None:
    spec = _cover(
        provenance=[
            {"path": "title", "sourceChapterIds": ["1"]},
            {"path": "subtitle", "sourceChapterIds": ["1"]},
            {"path": "sectionLabel", "sourceChapterIds": ["1"]},
            {"path": "statBadges[0].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[0].label", "sourceChapterIds": ["1"]},
            {"path": "missing.field", "sourceChapterIds": ["1"]},
        ]
    )

    repaired = repair_live_slide_spec(spec, _request(chapters=("1",)))

    paths = {entry["path"] for entry in repaired["fieldProvenance"]}
    assert "missing.field" not in paths


def test_cover_keeps_only_three_stat_badges() -> None:
    spec = _cover(
        statBadges=[
            {"value": "80%", "label": "Automation rate"},
            {"value": "12 weeks", "label": "Duration"},
            {"value": "4", "label": "Team size"},
            {"value": "99%", "label": "Extra one"},
            {"value": "1", "label": "Extra two"},
        ],
        provenance=[
            {"path": "title", "sourceChapterIds": ["1"]},
            {"path": "subtitle", "sourceChapterIds": ["1"]},
            {"path": "sectionLabel", "sourceChapterIds": ["1"]},
            {"path": "statBadges[0].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[0].label", "sourceChapterIds": ["1"]},
            {"path": "statBadges[1].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[1].label", "sourceChapterIds": ["1"]},
            {"path": "statBadges[2].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[2].label", "sourceChapterIds": ["1"]},
            {"path": "statBadges[3].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[3].label", "sourceChapterIds": ["1"]},
            {"path": "statBadges[4].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[4].label", "sourceChapterIds": ["1"]},
        ],
    )

    repaired = repair_live_slide_spec(spec, _request(chapters=("1",)))

    assert len(repaired["statBadges"]) == 3
    paths = {entry["path"] for entry in repaired["fieldProvenance"]}
    assert "statBadges[3].value" not in paths
    assert "statBadges[2].value" in paths


def test_group_a_multi_chapter_stamps_required_title_with_request_chapters() -> None:
    """BT-10/BT-14: CONTEXT title traces to both chapters the generator was given."""
    request = StructuredGenerationRequest(
        layout_id="CONTEXT_01",
        chapters=(
            {"chapter_id": "1", "title": "Management summary", "body": [{"text": "Agent takes over matching"}]},
            {"chapter_id": "2", "title": "Starting point", "body": [{"text": "Invoices are checked by hand"}]},
        ),
        target_schema={
            "type": "object",
            "required": [
                "schema_version",
                "layoutId",
                "title",
                "sourceChapterIds",
                "problem",
                "solution",
                "currentState",
                "targetState",
            ],
        },
        instructions="Generate CONTEXT_01.",
    )
    spec = {
        "schema_version": "1.0",
        "layoutId": "CONTEXT_01",
        "sectionLabel": "CONTEXT",
        "title": "Invoice matching today",
        "sourceChapterIds": ["2"],
        "problem": {"title": "Problem", "description": "Invoice checks are manual."},
        "solution": {"title": "Solution", "description": "Automate the rule-based checks."},
        "currentState": {"title": "Current state", "description": "Every invoice needs review."},
        "targetState": {"title": "Target state", "description": "Only exceptions need review."},
        "fieldProvenance": [
            {"path": "problem.title", "sourceChapterIds": ["2"]},
            {"path": "problem.description", "sourceChapterIds": ["2"]},
            {"path": "solution.title", "sourceChapterIds": ["1"]},
            {"path": "solution.description", "sourceChapterIds": ["1"]},
            {"path": "currentState.title", "sourceChapterIds": ["2"]},
            {"path": "currentState.description", "sourceChapterIds": ["2"]},
            {"path": "targetState.title", "sourceChapterIds": ["1"]},
            {"path": "targetState.description", "sourceChapterIds": ["1"]},
        ],
    }

    repaired = repair_live_slide_spec(spec, request)

    assert "sectionLabel" not in repaired
    title_entry = next(
        entry for entry in repaired["fieldProvenance"] if entry["path"] == "title"
    )
    assert title_entry["sourceChapterIds"] == ["1", "2"]
    assert set(repaired["sourceChapterIds"]) == {"1", "2"}
    validate_field_provenance(
        repaired,
        real_chapter_ids=("1", "2"),
        allowed_chapter_ids=("1", "2"),
    )


def test_group_b_schema_without_field_provenance_strips_the_key() -> None:
    request = StructuredGenerationRequest(
        layout_id="PROCESS_FLOW_01",
        chapters=(
            {"chapter_id": "2", "title": "As-is", "body": []},
            {"chapter_id": "4", "title": "To-be", "body": []},
        ),
        target_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "schema_version": {"type": "string"},
                "layoutId": {"type": "string"},
                "title": {"type": "string"},
                "sourceChapterIds": {"type": "array"},
                "phases": {"type": "array"},
            },
            "required": ["schema_version", "layoutId", "title", "sourceChapterIds", "phases"],
        },
        instructions="Generate PROCESS_FLOW_01.",
    )
    spec = {
        "schema_version": "1.0",
        "layoutId": "PROCESS_FLOW_01",
        "title": "To-be process",
        "sourceChapterIds": ["2", "4"],
        "phases": [{"number": 1, "name": "Capture", "description": "Read the invoice"}],
        "fieldProvenance": [
            {"path": "title", "sourceChapterIds": ["2"]},
            {"path": "phases[0].name", "sourceChapterIds": ["2"]},
        ],
        "unexpected": True,
    }

    repaired = repair_live_slide_spec(spec, request)

    assert "fieldProvenance" not in repaired
    assert "unexpected" not in repaired
    assert repaired["title"] == "To-be process"
    assert repaired["sourceChapterIds"] == ["2", "4"]


def test_non_group_a_does_not_invent_required_multi_chapter_provenance() -> None:
    request = StructuredGenerationRequest(
        layout_id="ARCHITECTURE_01",
        chapters=(
            {"chapter_id": "6", "title": "Build", "body": []},
            {"chapter_id": "7", "title": "Need", "body": []},
        ),
        target_schema={
            "type": "object",
            "required": ["schema_version", "layoutId", "title", "sourceChapterIds", "components"],
        },
        instructions="Generate ARCHITECTURE_01.",
    )
    spec = {
        "schema_version": "1.0",
        "layoutId": "ARCHITECTURE_01",
        "title": "How it is built",
        "sourceChapterIds": ["6"],
        "components": [{"number": 1, "title": "ERP", "description": "Orders"}],
        "fieldProvenance": [
            {"path": "components[0].number", "sourceChapterIds": ["6"]},
            {"path": "components[0].title", "sourceChapterIds": ["6"]},
            {"path": "components[0].description", "sourceChapterIds": ["6"]},
        ],
    }

    repaired = repair_live_slide_spec(spec, request)

    paths = {entry["path"] for entry in repaired["fieldProvenance"]}
    assert "title" not in paths


def test_wrapper_accepts_context_after_required_title_stamp() -> None:
    calls: list[str] = []

    def incomplete(request: StructuredGenerationRequest) -> dict[str, Any]:
        calls.append(request.layout_id)
        return {
            "schema_version": "1.0",
            "layoutId": "CONTEXT_01",
            "title": "Invoice matching today",
            "sourceChapterIds": ["1", "2"],
            "problem": {"title": "Problem", "description": "Invoice checks are manual."},
            "solution": {"title": "Solution", "description": "Automate the rule-based checks."},
            "currentState": {"title": "Current state", "description": "Every invoice needs review."},
            "targetState": {"title": "Target state", "description": "Only exceptions need review."},
            "fieldProvenance": [
                {"path": "problem.title", "sourceChapterIds": ["2"]},
                {"path": "problem.description", "sourceChapterIds": ["2"]},
                {"path": "solution.title", "sourceChapterIds": ["1"]},
                {"path": "solution.description", "sourceChapterIds": ["1"]},
                {"path": "currentState.title", "sourceChapterIds": ["2"]},
                {"path": "currentState.description", "sourceChapterIds": ["2"]},
                {"path": "targetState.title", "sourceChapterIds": ["1"]},
                {"path": "targetState.description", "sourceChapterIds": ["1"]},
            ],
        }

    request = StructuredGenerationRequest(
        layout_id="CONTEXT_01",
        chapters=(
            {"chapter_id": "1", "title": "Management summary", "body": [{"text": "Agent takes over matching"}]},
            {"chapter_id": "2", "title": "Starting point", "body": [{"text": "Invoices are checked by hand"}]},
        ),
        target_schema={
            "type": "object",
            "required": [
                "schema_version",
                "layoutId",
                "title",
                "sourceChapterIds",
                "problem",
                "solution",
                "currentState",
                "targetState",
            ],
        },
        instructions="Generate CONTEXT_01.",
    )
    result = wrap_live_structured_generator(incomplete)(request)

    assert len(calls) == 1
    assert next(entry["sourceChapterIds"] for entry in result["fieldProvenance"] if entry["path"] == "title") == [
        "1",
        "2",
    ]


def test_bt14_timeline_rejects_ungrounded_10() -> None:
    from services.slides.content_generation.group_b.common import UngroundedContentError
    from services.slides.content_generation.group_b.timeline_01 import generate_timeline_01

    root = Path(__file__).resolve().parents[3]
    framework = json.loads(
        (root / "tests" / "fixtures" / "framework_object.confirmed.group_b.json").read_text(
            encoding="utf-8"
        )
    )
    for chapter in framework["chapters"]:
        if str(chapter.get("chapter_id")) == "10":
            chapter["body"] = "ten weeks for implementation"
    spec = {
        "schema_version": "1.0",
        "layoutId": "TIMELINE_01",
        "title": "Implementation roadmap",
        "sourceChapterIds": ["10"],
        "phases": [
            {"id": "p1", "name": "Build", "description": "10 weeks for implementation"},
        ],
        "milestones": [
            {"id": "m1", "name": "Access confirmed", "phaseId": "p1", "date": "Start"},
        ],
    }

    def generate(_request: StructuredGenerationRequest) -> dict[str, Any]:
        return spec

    with pytest.raises(UngroundedContentError) as exc_info:
        generate_timeline_01(
            framework,
            structured_generate=generate,
            compress_fields=lambda values, _violations: values,
        )
    assert "10" in str(exc_info.value)


def test_sanitizer_runs_for_all_layouts() -> None:
    """Sanitizer rewrites ungrounded compounds for SCOPE_01 and TIMELINE_01."""
    scope_request = StructuredGenerationRequest(
        layout_id="SCOPE_01",
        chapters=(
            {"chapter_id": "3", "title": "Aim", "body": "handles seventy percent of cases"},
            {"chapter_id": "5", "title": "Detail", "body": "reduces manual effort significantly"},
        ),
        target_schema={
            "type": "object",
            "properties": {
                "schema_version": {"type": "string"},
                "layoutId": {"type": "string"},
                "title": {"type": "string"},
                "sourceChapterIds": {"type": "array"},
                "included": {"type": "array"},
                "later": {"type": "array"},
                "fieldProvenance": {"type": "array"},
            },
            "required": ["schema_version", "layoutId", "title", "sourceChapterIds", "included", "later"],
        },
        instructions="Generate SCOPE_01.",
    )
    scope_spec = {
        "schema_version": "1.0",
        "layoutId": "SCOPE_01",
        "title": "First release scope",
        "sourceChapterIds": ["3", "5"],
        "included": ["Mailbox intake", "Handles 70% of cases"],
        "later": ["Supplier messages"],
        "fieldProvenance": [
            {"path": "title", "sourceChapterIds": ["3", "5"]},
            {"path": "included[0]", "sourceChapterIds": ["3"]},
            {"path": "included[1]", "sourceChapterIds": ["3"]},
            {"path": "later[0]", "sourceChapterIds": ["5"]},
        ],
    }
    scope = wrap_live_structured_generator(lambda _request: scope_spec)(scope_request)
    assert "70%" not in scope["included"][1]
    assert "seventy percent" in scope["included"][1]

    timeline_request = StructuredGenerationRequest(
        layout_id="TIMELINE_01",
        chapters=(
            {"chapter_id": "10", "title": "Plan", "body": "ten weeks for implementation"},
        ),
        target_schema={
            "type": "object",
            "properties": {
                "schema_version": {"type": "string"},
                "layoutId": {"type": "string"},
                "title": {"type": "string"},
                "sourceChapterIds": {"type": "array"},
                "phases": {"type": "array"},
                "milestones": {"type": "array"},
            },
            "required": ["schema_version", "layoutId", "title", "sourceChapterIds", "phases", "milestones"],
        },
        instructions="Generate TIMELINE_01.",
    )
    timeline_spec = {
        "schema_version": "1.0",
        "layoutId": "TIMELINE_01",
        "title": "Implementation roadmap",
        "sourceChapterIds": ["10"],
        "phases": [{"id": "p1", "name": "Build", "description": "10 weeks for implementation"}],
        "milestones": [{"id": "m1", "name": "Access confirmed", "phaseId": "p1", "date": "Start"}],
    }
    timeline = wrap_live_structured_generator(lambda _request: timeline_spec)(timeline_request)
    assert "fieldProvenance" not in timeline
    assert "10 weeks" not in timeline["phases"][0]["description"]
    assert "ten weeks" in timeline["phases"][0]["description"]


def test_wrapper_retries_then_returns_repaired_cover() -> None:
    calls: list[str] = []

    def flaky(request: StructuredGenerationRequest) -> dict[str, Any]:
        calls.append(request.instructions)
        return _cover()

    generate = wrap_live_structured_generator(flaky)
    result = generate(_request(chapters=("1",)))

    assert result["sectionLabel"] == "AUTOMATION"
    assert any(entry["path"] == "sectionLabel" for entry in result["fieldProvenance"])
    assert len(calls) == 1
