"""Locale-aware Group A numeric grounding — digit forms only, not word-to-digit."""

from __future__ import annotations

import pytest

from llm.client import _apply_compression_number_forms, _introduced_semantic_numbers
from services.slides.content_generation.group_a.common import UngroundedContentError
from tests.unit.slides.test_group_a_content_generation import (
    build_context_01_spec,
    validate_group_a_content,
)


def test_grounding_accepts_eu_dot_thousands_when_chapter_has_plain_digits() -> None:
    spec = build_context_01_spec(
        problem_description="About 12.000 invoices per month are processed manually.",
        problem_provenance=["1"],
        chapter_bodies={
            "1": "The team processes 12000 invoices per month in SAP.",
            "2": "Analysts manually compare invoices, purchase orders, and goods receipts.",
        },
    )
    result = validate_group_a_content(spec)
    assert result.status == "VALID"


def test_grounding_accepts_plain_digits_when_chapter_has_eu_dot_thousands() -> None:
    spec = build_context_01_spec(
        problem_description="About 12000 invoices per month are processed manually.",
        problem_provenance=["1"],
        chapter_bodies={
            "1": "The team processes 12.000 invoices per month in SAP.",
            "2": "Analysts manually compare invoices, purchase orders, and goods receipts.",
        },
    )
    result = validate_group_a_content(spec)
    assert result.status == "VALID"


def test_grounding_accepts_comma_thousands_when_chapter_has_plain_digits() -> None:
    spec = build_context_01_spec(
        problem_description="About 12,000 invoices per month are processed manually.",
        problem_provenance=["1"],
        chapter_bodies={
            "1": "The team processes 12000 invoices per month in SAP.",
            "2": "Analysts manually compare invoices, purchase orders, and goods receipts.",
        },
    )
    result = validate_group_a_content(spec)
    assert result.status == "VALID"


def test_grounding_rejects_digit_form_when_chapter_has_words_only() -> None:
    spec = build_context_01_spec(
        problem_description="About 12.000 invoices per month are processed manually.",
        problem_provenance=["1"],
        chapter_bodies={
            "1": "The team processes twelve thousand invoices per month in SAP.",
            "2": "Analysts manually compare invoices, purchase orders, and goods receipts.",
        },
    )
    with pytest.raises(UngroundedContentError, match="problem.description"):
        validate_group_a_content(spec)


def test_grounding_rejects_different_numeric_value() -> None:
    spec = build_context_01_spec(
        problem_description="About 15000 invoices per month are processed manually.",
        problem_provenance=["1"],
        chapter_bodies={
            "1": "The team processes 12000 invoices per month in SAP.",
            "2": "Analysts manually compare invoices, purchase orders, and goods receipts.",
        },
    )
    with pytest.raises(UngroundedContentError, match="problem.description"):
        validate_group_a_content(spec)


def test_grounding_does_not_borrow_digits_from_unattributed_chapter() -> None:
    spec = build_context_01_spec(
        problem_description="About 12.000 invoices per month are processed manually.",
        problem_provenance=["2"],
        chapter_bodies={
            "1": "The team processes 12000 invoices per month in SAP.",
            "2": "Analysts manually compare invoices, purchase orders, and goods receipts.",
        },
    )
    with pytest.raises(UngroundedContentError, match="problem.description"):
        validate_group_a_content(spec)


def test_compression_rejects_introduced_eu_thousands_from_word_only_field() -> None:
    original = "Zwölftausend Rechnungen werden monatlich manuell verarbeitet"
    rewritten = "12.000 Rechnungen monatlich manuell"
    assert _apply_compression_number_forms(original, rewritten, 160) == original


def test_compression_keeps_grounded_eu_thousands_equivalent_rewrite() -> None:
    original = "12.000 Rechnungen werden monatlich manuell verarbeitet"
    rewritten = "12000 Rechnungen monatlich"
    result = _apply_compression_number_forms(original, rewritten, 160)
    assert _introduced_semantic_numbers(original, result) == set()
    assert "12000" not in result or "12.000" in result


def test_compression_rejects_unrelated_thousands_rewrite() -> None:
    original = "12.000 Rechnungen werden monatlich manuell verarbeitet"
    rewritten = "15.000 Rechnungen monatlich"
    assert _apply_compression_number_forms(original, rewritten, 160) == original
