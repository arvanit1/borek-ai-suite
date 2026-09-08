"""JJ-26: the single branded template, its named slots, and their chapter feeds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from services.gamma.contract import (
    ALLOWED_CONTENT_SLOTS,
    FORBIDDEN_BRANDING_KEYS,
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaGenerateRequest,
    GammaPayloadError,
)
from services.gamma.fixture_client import FixtureGammaClient, validate_generate_request
from services.gamma.slot_mapping import build_gamma_content_slots, slot_chapter_provenance
from services.gamma.template import load_gamma_template
from services.slides.group_b_source_chapters import GROUP_B_ALLOWED_CHAPTER_IDS
from services.slides.group_c_source_chapters import GROUP_C_ALLOWED_CHAPTER_IDS

ROOT = Path(__file__).resolve().parents[3]
EGRESS_POLICY_PATH = ROOT / "config" / "data_egress_policy.yaml"
LAYOUT_REGISTRY_PATH = ROOT / "packages" / "contracts" / "layout_registry.json"

# The Group A and summary generators keep their allowances inline rather than in
# a shared map, so they are mirrored here to keep the assertion honest.
GROUP_A_ALLOWED_CHAPTER_IDS = {
    "COVER_01": ("1",),
    "CONTEXT_01": ("1", "2"),
    "PROBLEM_SOLUTION_01": ("2", "4"),
    "SCOPE_01": ("3", "5"),
    "REQUIREMENTS_MATRIX_01": ("5",),
    "EXECUTIVE_SUMMARY_01": ("1",),
}
LAYOUT_CHAPTER_ALLOWANCES = {
    **GROUP_A_ALLOWED_CHAPTER_IDS,
    **GROUP_B_ALLOWED_CHAPTER_IDS,
    **GROUP_C_ALLOWED_CHAPTER_IDS,
}


def _framework(bodies: dict[str, str]) -> dict[str, object]:
    return {
        "status": "confirmed",
        "chapters": [
            {"chapter_id": chapter_id, "title": f"Chapter {chapter_id}", "body": body}
            for chapter_id, body in bodies.items()
        ]
    }


def test_template_identity_is_locked_to_one_branded_deck() -> None:
    template = load_gamma_template()
    assert template.template_id == LOCKED_BOREK_TEMPLATE_ID == "borek-branded-standard"
    assert template.template_version == LOCKED_BOREK_TEMPLATE_VERSION == "v1"
    assert template.branding_locked is True
    assert FORBIDDEN_BRANDING_KEYS >= {"brand_color", "theme", "font", "logo_override"}
    assert not FORBIDDEN_BRANDING_KEYS & ALLOWED_CONTENT_SLOTS


def test_every_card_maps_to_a_real_layout_and_declares_its_slots() -> None:
    template = load_gamma_template()
    registry = json.loads(LAYOUT_REGISTRY_PATH.read_text(encoding="utf-8"))["layouts"]
    card_layouts = [card.layout_id for card in template.cards]

    assert card_layouts, "the template must define its cards"
    assert set(card_layouts) <= set(registry)
    assert len(card_layouts) == len(set(card_layouts)), "one card per layout"
    assert [card.card for card in template.cards] == list(range(1, len(template.cards) + 1))

    slots_on_cards = {name for card in template.cards for name in card.slots}
    assert slots_on_cards == set(template.slot_names), "every slot belongs to a card"


def test_slot_chapters_stay_within_the_layout_allowance_of_the_internal_renderer() -> None:
    """Both engines must cite the same Framework evidence for a given layout."""
    for slot in load_gamma_template().slots:
        allowed = set(LAYOUT_CHAPTER_ALLOWANCES[slot.layout_id])
        assert set(slot.source_chapter_ids) <= allowed, slot.name


def test_success_metrics_excludes_the_business_case_chapter() -> None:
    """MS-14 forbids currency here and Gamma output skips the SlideSpec validator."""
    slot = load_gamma_template().slot("success_metrics.body")
    assert "9" not in slot.source_chapter_ids


def test_every_slot_is_classified_and_client_text_is_allow_listed_for_gamma() -> None:
    policy = yaml.safe_load(EGRESS_POLICY_PATH.read_text(encoding="utf-8"))
    classifications = policy["field_classifications"]
    gamma_allowlist = set(policy["client_confidential_allowlist"]["gamma"])

    for slot in load_gamma_template().slots:
        path = f"/slots/{slot.name}"
        assert classifications.get(path) == slot.classification, path
        if slot.classification == "client_confidential":
            assert path in gamma_allowlist, path
        if slot.is_chapter_fed:
            assert slot.classification == "client_confidential", slot.name


def test_slots_are_filled_from_the_mapped_chapters_only() -> None:
    framework = _framework(
        {
            "1": "Management summary text.",
            "2": "The process today.",
            "8": "Security posture.",
            "9": "Payback in 14 months at EUR 120,000 saved.",
        }
    )
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=framework,
    )
    by_name = {slot.name: slot.value for slot in slots}

    assert by_name["cover.title"] == "Invoice 3-way Match"
    assert by_name["cover.client_name"] == "Acme"
    assert by_name["cover.subtitle"] == "Management summary text."
    assert by_name["context.summary"] == "Management summary text.\n\nThe process today."
    assert by_name["compliance.body"] == "Security posture."
    # Chapter 9 feeds nothing, so the ROI figure never reaches the deck.
    assert not any("120,000" in value for value in by_name.values())


def test_slots_without_grounded_chapters_are_omitted_not_padded() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_framework({"13": "Confirm the pilot scope."}),
    )
    names = [slot.name for slot in slots]
    assert names == ["cover.title", "cover.client_name", "next_steps.body"]


def test_structured_chapter_bodies_are_flattened_to_text() -> None:
    framework = {
        "status": "confirmed",
        "chapters": [
            {
                "chapter_id": "10",
                "title": "Complexity, effort & timeline",
                "body": [{"phase": "Discovery", "duration": "3 weeks"}],
            }
        ]
    }
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=framework,
    )
    timeline = next(slot for slot in slots if slot.name == "timeline.body")
    assert timeline.value == "Discovery\n3 weeks"


def test_long_chapters_are_trimmed_to_the_slot_limit_at_a_boundary() -> None:
    template = load_gamma_template()
    limit = template.slot("executive_summary.body").max_chars
    sentence = "Automating the three-way match removes manual reconciliation. "
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_framework({"1": sentence * 100}),
    )
    summary = next(slot for slot in slots if slot.name == "executive_summary.body")
    assert len(summary.value) <= limit
    assert summary.value.endswith(".")


def test_a_missing_required_slot_stops_the_pipeline() -> None:
    with pytest.raises(GammaPayloadError, match="cover.client_name"):
        build_gamma_content_slots(
            opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": ""},
        )


def test_provenance_reports_the_chapters_behind_each_sent_slot() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_framework({"1": "Summary.", "2": "Today."}),
    )
    provenance = slot_chapter_provenance(slots)
    assert provenance["context.summary"] == ("1", "2")
    assert provenance["cover.title"] == ()


def test_the_provider_accepts_a_full_contract_request() -> None:
    slots = build_gamma_content_slots(
        opportunity={"opportunity_name": "Invoice 3-way Match", "client_name": "Acme"},
        framework=_framework({str(index): f"Chapter {index} body." for index in range(14)}),
    )
    request = GammaGenerateRequest(
        template_id=LOCKED_BOREK_TEMPLATE_ID,
        template_version=LOCKED_BOREK_TEMPLATE_VERSION,
        opportunity_id="opp-1",
        presentation_version_id="ver-1",
        output_formats=("pptx",),
        slots=slots,
        timeout_seconds=30.0,
    )
    validate_generate_request(request)
    result = FixtureGammaClient().generate(request)
    assert result.branding_locked is True
    assert len(slots) == len(load_gamma_template().slots)
