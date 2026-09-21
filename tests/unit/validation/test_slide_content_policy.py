"""Offline status entailment and German prose regressions, including live evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.validation.slide_content_policy import (
    ContentPolicyError,
    validate_content_policy,
)

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = json.loads(
    (ROOT / "tests/fixtures/slides/content_policy_recorded_failures.json").read_text(
        encoding="utf-8"
    )
)
CLAIM = "Die erste Automatisierungsstufe ist implementiert, mit einem Human in the Loop für Ausnahmen."


def check(text, source="", language="en", *, extra_chapter=None):
    spec = {
        "description": text,
        "sourceChapterIds": ["1", "2"],
        "fieldProvenance": [{"path": "description", "sourceChapterIds": ["1"]}],
    }
    chapters = ({"chapter_id": "1", "body": source},)
    if extra_chapter:
        chapters += ({"chapter_id": "2", "body": extra_chapter},)
    validate_content_policy(spec, chapters, language)


def test_exact_recorded_claim_is_rejected_against_actual_attributed_chapter():
    assert EVIDENCE["summary"]["highlights"][2]["description"] == CLAIM
    chapter = EVIDENCE["chapter_1"]
    assert "Fortfahren zu Stufe 2" in json.dumps(chapter, ensure_ascii=False)
    with pytest.raises(ContentPolicyError, match=r"highlights\[2\].description"):
        validate_content_policy(EVIDENCE["summary"], (chapter,), "de")


@pytest.mark.parametrize(
    "text",
    [
        "Automation has been implemented.",
        "The automation is completed.",
        "Automation was deployed without errors.",
        "Die Automatisierung ist implementiert.",
        "Die Automatisierung wurde umgesetzt.",
        "Die Automatisierung ist bereits in Betrieb.",
    ],
)
@pytest.mark.parametrize(
    "source",
    [
        "Automation is planned. Die Automatisierung ist geplant.",
        "Automation is being implemented. Die Automatisierung wird umgesetzt.",
        "Automation is not implemented. Die Automatisierung ist nicht implementiert.",
        "Automation is partially implemented. Die Automatisierung ist teilweise implementiert.",
    ],
)
def test_completed_assertion_needs_completed_source(text, source):
    with pytest.raises(ContentPolicyError, match="Unsupported implementation"):
        check(text, source)


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        (CLAIM, "Die erste Automatisierungsstufe wurde erfolgreich implementiert."),
        ("Automation is implemented.", "The automation was implemented last year."),
        ("Automation is implemented.", "The automation was successfully implemented."),
        (
            "Die Automatisierung ist umgesetzt.",
            "Die Automatisierung wurde im Mai umgesetzt.",
        ),
        ("Automation is completed.", "The team has completed the automation."),
        ("We implemented automation.", "Automation has been implemented."),
        (
            "Die Automatisierung ist umgesetzt.",
            "Wir haben die Automatisierung umgesetzt.",
        ),
        ("Automation is implemented without errors.", "Automation is implemented."),
        ("The migration is completed.", [{"label": "Migration", "value": "completed"}]),
    ],
)
def test_explicit_completed_evidence_is_accepted(claim, source):
    check(claim, source)


@pytest.mark.parametrize(
    "text",
    [
        "Automation is not implemented.",
        "Automation has never been implemented.",
        "Automation should be implemented.",
        "Automation will be implemented.",
        "If approved, automation is implemented.",
        "Automation is implemented if approved.",
        "Automation is being implemented.",
        "Automation is planned to be implemented.",
        "Automation to be implemented.",
        "Die Automatisierung ist nicht implementiert.",
        "Automation is implemented only after approval.",
        "Die Automatisierung soll implementiert werden.",
        "Falls genehmigt, wird die Automatisierung implementiert.",
        "Die Automatisierung wird gerade implementiert.",
        "Die Automatisierung ist geplant.",
        "Die Bearbeitung erfolgt manuell.",
    ],
)
def test_non_completed_status_is_not_mistaken_for_asserted_completion(text):
    check(text, "Manual processing today. Die Bearbeitung erfolgt manuell.")


def test_unrelated_field_chapter_does_not_supply_completion_evidence():
    with pytest.raises(ContentPolicyError):
        check(
            "Automation is implemented.",
            "Automation is planned.",
            extra_chapter="Automation is implemented.",
        )


@pytest.mark.parametrize(
    "source",
    [
        "The migration is completed.",
        "Die zweite Automatisierungsstufe ist implementiert.",
        {"block": "callout", "kind": "recommendation", "text": CLAIM},
        {"label": "Zielzustand", "value": CLAIM},
        {"block": "callout", "kind": "recommendation", "text": "Zielbild. " + CLAIM},
    ],
)
def test_other_work_stage_or_recommendation_is_not_evidence(source):
    with pytest.raises(ContentPolicyError):
        check(CLAIM, source)


def test_unrelated_negation_does_not_hide_completed_assertion():
    with pytest.raises(ContentPolicyError):
        check("Samples are not available, but automation is implemented.")


def test_each_completed_clause_requires_its_own_source_evidence():
    with pytest.raises(ContentPolicyError):
        check(
            "Migration is completed and automation is implemented.",
            "Migration is completed.",
        )


def test_completed_documentation_does_not_establish_completed_automation():
    with pytest.raises(ContentPolicyError):
        check("Automation is implemented.", "Automation documentation is completed.")


def test_missing_field_attribution_is_not_replaced_by_root_chapters():
    with pytest.raises(ContentPolicyError):
        validate_content_policy(
            {"title": "Automation is implemented.", "sourceChapterIds": ["1"]},
            ({"chapter_id": "1", "body": "Automation is implemented."},),
        )


def test_raw_recorded_english_context_fails_german_policy():
    with pytest.raises(ContentPolicyError, match="German output required"):
        validate_content_policy(EVIDENCE["context"], (EVIDENCE["chapter_1"],), "de")


def test_recorded_summary_is_rejected_by_the_full_owner_validator():
    from services.slides.content_generation.group_a.common import (
        ContentPolicyValidationError,
        _validate_slide_spec,
    )
    from services.slides.content_generation.summary.executive_summary_01 import CONFIG

    with pytest.raises(
        ContentPolicyValidationError, match=r"highlights\[2\].description"
    ):
        _validate_slide_spec(
            EVIDENCE["summary"], CONFIG, (EVIDENCE["chapter_1"],), "de"
        )


def test_raw_recorded_english_context_remains_valid_for_english_policy():
    validate_content_policy(EVIDENCE["context"], (EVIDENCE["chapter_1"],), "en")


@pytest.mark.parametrize(
    "text",
    [
        "Der Prozess nutzt SAP S/4HANA, Microsoft Dynamics und OpenAI APIs.",
        "Human in the Loop, Single Sign-On und Proof of Concept bleiben vorgesehen.",
        "Das Team plant End-to-End-Automatisierung mit ERP, OCR und RPA.",
        "The North Face",
        "Microsoft Power Automate",
        "API / ERP / SQL",
        'Das Quellzitat lautet: "Every invoice needs review before booking."',
        "Die Quelle sagt: „Automation is implemented.“",
    ],
)
def test_german_business_terms_names_and_attributed_quotes_are_allowed(text):
    check(text, text, "de")


def test_an_unattributed_english_quote_does_not_bypass_language_check():
    with pytest.raises(ContentPolicyError, match="German output required"):
        check(
            '"Every invoice needs review before booking."', "Manuelle Bearbeitung", "de"
        )
