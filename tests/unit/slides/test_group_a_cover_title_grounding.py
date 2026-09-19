"""COVER_01 title/subtitle numeric grounding and retry guidance."""

from __future__ import annotations

import copy

import pytest

from services.slides.content_generation.group_a.common import UngroundedContentError
from services.slides.content_generation.group_a.cover_01 import (
    _cover_retry_message,
    repair_cover_ungrounded_stat_badges,
)
from tests.unit.slides.test_group_a_content_generation import (
    CASES,
    CapturingGenerator,
    SequenceCapturingGenerator,
    _cover_chapters,
    _cover_without_numeric_title_fields,
    _framework,
    _run,
    _slide,
)

_WORD_ONLY_BODY = (
    "about twelve thousand invoices per month in SAP with human-controlled exceptions"
)
_DIGIT_GROUNDED_BODY = "The team processes 12000 invoices per month in SAP."


def _patch_chapter_body(monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    from services.slides.content_generation.group_a import common as group_a_common

    monkeypatch.setattr(
        group_a_common,
        "_extract_allowed_chapters",
        lambda _framework_object, _allowed: (
            {
                "chapter_id": "1",
                "title": "Management summary",
                "body": body,
            },
        ),
    )


def _cover_spec(
    *,
    title: str,
    subtitle: str | None = None,
    section_label: str | None = None,
    title_provenance: list[str] | None = None,
) -> dict:
    cover = _cover_without_numeric_title_fields(_slide(CASES["cover"]))
    cover["title"] = title
    if subtitle is not None:
        cover["subtitle"] = subtitle
    if section_label is not None:
        cover["sectionLabel"] = section_label
    cover["statBadges"] = [{"value": "Human", "label": "Exceptions stay controlled"}]
    provenance = [
        entry
        for entry in cover["fieldProvenance"]
        if not str(entry["path"]).startswith("statBadges[")
    ]
    for entry in provenance:
        if entry["path"] == "title" and title_provenance is not None:
            entry["sourceChapterIds"] = list(title_provenance)
    provenance.extend(
        [
            {"path": "statBadges[0].value", "sourceChapterIds": ["1"]},
            {"path": "statBadges[0].label", "sourceChapterIds": ["1"]},
        ]
    )
    cover["fieldProvenance"] = provenance
    return cover


def test_cover_title_rejects_eu_thousands_from_word_only_chapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_chapter_body(monkeypatch, _WORD_ONLY_BODY)
    cover = _cover_spec(title="Automatisierung für 12.000 Rechnungen pro Monat")

    with pytest.raises(UngroundedContentError, match="title"):
        _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))


def test_cover_title_retry_accepts_grounded_non_numeric_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_chapter_body(monkeypatch, _WORD_ONLY_BODY)
    bad = _cover_spec(title="Automatisierung für 12.000 Rechnungen pro Monat")
    good = copy.deepcopy(bad)
    good["title"] = "Kontrollierte Rechnungsautomatisierung"
    generator = SequenceCapturingGenerator(outputs=[bad, good])

    result = _run(CASES["cover"], _framework(), generator)

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["title"] == "Kontrollierte Rechnungsautomatisierung"


def test_cover_title_retry_feedback_names_failed_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_chapter_body(monkeypatch, _WORD_ONLY_BODY)
    bad = _cover_spec(title="Automatisierung für 12.000 Rechnungen pro Monat")
    good = copy.deepcopy(bad)
    good["title"] = "Kontrollierte Rechnungsautomatisierung"
    generator = SequenceCapturingGenerator(outputs=[bad, good])

    _run(CASES["cover"], _framework(), generator)

    assert len(generator.requests) >= 2
    retry = generator.requests[1].instructions
    assert "title" in retry.casefold()
    assert "word-form quantities" in retry
    assert "non-numeric" in retry.casefold()


def test_cover_title_accepts_eu_thousands_when_chapter_has_plain_digits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_chapter_body(monkeypatch, _DIGIT_GROUNDED_BODY)
    cover = _cover_spec(title="Automatisierung für 12.000 Rechnungen pro Monat")

    result = _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert "12.000" in result.slide_spec["title"]


def test_cover_title_rejects_different_numeric_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_chapter_body(monkeypatch, _DIGIT_GROUNDED_BODY)
    cover = _cover_spec(title="Automatisierung für 15.000 Rechnungen pro Monat")

    with pytest.raises(UngroundedContentError, match="title"):
        _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))


def test_cover_subtitle_rejects_ungrounded_digits_from_word_only_chapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_chapter_body(monkeypatch, _WORD_ONLY_BODY)
    cover = _cover_spec(
        title="Kontrollierte Rechnungsautomatisierung",
        subtitle="Etwa 12.000 Rechnungen pro Monat",
    )

    with pytest.raises(UngroundedContentError, match="subtitle"):
        _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))


def test_cover_section_label_rejects_ungrounded_digits_from_word_only_chapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_chapter_body(monkeypatch, _WORD_ONLY_BODY)
    cover = _cover_spec(
        title="Kontrollierte Rechnungsautomatisierung",
        section_label="12.000 RECHNUNGEN",
    )

    with pytest.raises(UngroundedContentError, match="sectionLabel"):
        _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))


def test_cover_retry_message_addresses_ungrounded_title() -> None:
    message = _cover_retry_message(
        "COVER_01 contains numeric content at title absent from its "
        "field-attributed chapters: 12.000"
    )

    assert "title" in message
    assert "word-form quantities" in message
    assert "non-numeric" in message.casefold()
    assert "Do not copy digit-form numbers from other chapters" in message


def test_cover_stat_badge_repair_remains_unchanged_for_valid_spec() -> None:
    cover = _slide(CASES["cover"])
    chapters = _cover_chapters()

    repaired = repair_cover_ungrounded_stat_badges(cover, chapters)

    assert repaired["statBadges"] == cover["statBadges"]
    assert repaired["title"] == cover["title"]


def test_valid_cover_fixture_is_not_modified() -> None:
    cover = _slide(CASES["cover"])

    result = _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["title"] == cover["title"]
    assert result.slide_spec["statBadges"] == cover["statBadges"]


def test_cover_title_retry_does_not_invent_commercial_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services.slides.content_generation.group_a.common import (
        ProhibitedCommercialContentError,
    )

    _patch_chapter_body(monkeypatch, _WORD_ONLY_BODY)
    cover = _cover_spec(title="Automatisierung mit EUR 80.000 Investition")

    with pytest.raises(ProhibitedCommercialContentError):
        _run(CASES["cover"], _framework(), CapturingGenerator(output=cover))
