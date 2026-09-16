"""Deterministic Borek CI voice validation for SlideSpec customer prose."""

from __future__ import annotations

import pytest

from services.validation.presentation_voice import (
    PresentationVoiceError,
    enforce_slide_spec_voice,
    lint_slide_spec_voice,
)


def _minimal_slide(**overrides: object) -> dict:
    base = {
        "schema_version": "1.0",
        "layoutId": "CONTEXT_01",
        "slideId": "slide-1",
        "sourceChapterIds": ["2"],
        "title": "Manual matching slows invoice release",
        "problem": {"title": "Problem", "description": "Checks are manual today."},
        "fieldProvenance": {"title": [{"path": "title", "sourceChapterIds": ["2"]}]},
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "term",
    [
        "leverage",
        "synergy",
        "synergies",
        "cutting-edge",
        "game-changing",
        "revolutionary",
        "disruptive",
        "best-in-class",
        "seamless",
        "holistic",
        "empower",
    ],
)
def test_banned_marketing_term_fails(term: str) -> None:
    slide = _minimal_slide(title=f"We will {term} the process.")
    errors = lint_slide_spec_voice(slide)
    assert errors
    with pytest.raises(PresentationVoiceError):
        enforce_slide_spec_voice(slide)


def test_normal_customer_prose_passes() -> None:
    slide = _minimal_slide(
        title="First-pass match reaches 75 percent with human review on exceptions.",
        problem={"title": "Problem", "description": "Analysts compare invoices manually."},
    )
    assert lint_slide_spec_voice(slide) == []


def test_exclamation_mark_fails() -> None:
    slide = _minimal_slide(title="Automation works!")
    assert lint_slide_spec_voice(slide)
    with pytest.raises(PresentationVoiceError, match="exclamation"):
        enforce_slide_spec_voice(slide)


def test_emoji_fails() -> None:
    slide = _minimal_slide(title="Automation works \U0001F680")
    assert lint_slide_spec_voice(slide)
    with pytest.raises(PresentationVoiceError, match="emoji"):
        enforce_slide_spec_voice(slide)


def test_internal_metadata_is_not_scanned() -> None:
    slide = _minimal_slide(
        title="Clean customer title",
        slideId="leverage-synergy-id",
        fieldProvenance={
            "title": [{"path": "title", "sourceChapterIds": ["2"]}],
        },
    )
    assert lint_slide_spec_voice(slide) == []


@pytest.mark.parametrize("term", ["Synergy", "Seamless", "Leverage", "Holistic"])
def test_standalone_banned_word_in_title_fails(term: str) -> None:
    slide = _minimal_slide(title=term)
    errors = lint_slide_spec_voice(slide)
    assert errors
    assert any("banned marketing term" in error for error in errors)
    with pytest.raises(PresentationVoiceError, match="banned marketing term"):
        enforce_slide_spec_voice(slide)


def test_standalone_banned_word_in_nested_customer_field_fails() -> None:
    slide = _minimal_slide(
        title="Manual matching today",
        problem={"title": "Seamless", "description": "Checks are manual today."},
    )
    errors = lint_slide_spec_voice(slide)
    assert any("problem.title" in error and "seamless" in error.lower() for error in errors)


def test_one_word_customer_title_passes() -> None:
    slide = _minimal_slide(title="Overview")
    assert lint_slide_spec_voice(slide) == []


def test_urls_in_customer_fields_are_ignored() -> None:
    slide = _minimal_slide(
        title="Manual matching today",
        problem={
            "title": "Reference",
            "description": "See https://example.com/file for the source diagram.",
        },
    )
    assert lint_slide_spec_voice(slide) == []


def test_metadata_ids_are_not_scanned() -> None:
    slide = {
        "schema_version": "1.0",
        "layoutId": "CONTEXT_01",
        "slideId": "slide-1",
        "sourceChapterIds": ["2"],
        "title": "Clean customer title",
        "problem": {
            "title": "Problem",
            "description": "Checks are manual today.",
        },
        "fieldProvenance": {
            "title": [{"path": "title", "sourceChapterIds": ["2"]}],
        },
        "reference": "artifact:abc123",
        "citation": "urn:test:abc",
    }
    assert lint_slide_spec_voice(slide) == []


def test_german_localized_prose_passes_voice_linter() -> None:
    slide = _minimal_slide(
        title="Erstpass-Abgleich erreicht 75 Prozent mit menschlicher Prüfung bei Ausnahmen.",
        problem={
            "title": "Ausgangslage",
            "description": "Analysten vergleichen Rechnungen manuell.",
        },
    )
    assert lint_slide_spec_voice(slide) == []
