"""Regression: scratch Gamma requests must honour one card per planned slide."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.gamma.contract import GammaContentSlot, GammaGenerateRequest, LOCKED_BOREK_TEMPLATE_ID, LOCKED_BOREK_TEMPLATE_VERSION
from services.gamma.input_text import (
    CARD_BREAK,
    CARD_SPLIT_INPUT_TEXT_BREAKS,
    align_slots_with_planned_slides,
    build_card_segments,
    build_scratch_input_text,
)
from services.gamma.live_client import LiveGammaClient, uses_scratch_generation
from services.gamma.template import load_gamma_template
from tests.unit.gamma.test_jj27_client_logo_placement import OPPORTUNITY_ID, _request
from tests.unit.gamma.test_jj29_signed_logo_url import OWNED_BASE, _mint
from services.gamma import live_client


ROOT = Path(__file__).resolve().parents[3]
NEXT_STEPS_FIXTURE = json.loads(
    (ROOT / "packages/contracts/fixtures/slide_spec/group_c/next_steps_01.realistic.json").read_text(
        encoding="utf-8"
    )
)


def _deepening_planned_specs(count: int) -> tuple[dict, ...]:
    layouts = load_gamma_template().profile("deepening").cards
    specs: list[dict] = []
    for index, layout_id in enumerate(layouts[:count]):
        if layout_id == "NEXT_STEPS_01":
            spec = dict(NEXT_STEPS_FIXTURE)
        else:
            spec = {"layoutId": layout_id, "title": f"Slide {index + 1}"}
        spec["layoutId"] = layout_id
        specs.append(spec)
    return tuple(specs)


def _scratch_payload(**overrides: object) -> dict:
    signed = _mint()
    assert signed is not None
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    request = _request(client_logo_ref=signed, **overrides)
    assert uses_scratch_generation(request) is True
    return client._generation_payload(request)  # noqa: SLF001


def test_scratch_payload_sets_card_split_and_num_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_client, "owned_https_prefixes", lambda: (f"{OWNED_BASE}/",))
    payload = _scratch_payload()

    assert payload["cardSplit"] == CARD_SPLIT_INPUT_TEXT_BREAKS
    assert payload["numCards"] >= 1
    if payload["numCards"] > 1:
        assert CARD_BREAK in payload["inputText"]
    assert payload["inputText"].count(CARD_BREAK) + 1 == payload["numCards"]


def test_nine_planned_slides_emit_nine_card_segments() -> None:
    planned = _deepening_planned_specs(9)
    slots = (
        GammaContentSlot("cover.title", "Demo"),
        GammaContentSlot("cover.client_name", "Acme"),
        GammaContentSlot("executive_summary.body", "Summary"),
        GammaContentSlot("next_steps.body", "Book a call."),
    )
    segments = build_card_segments(slots, planned_slide_specs=planned)
    assert len(segments) == 9


def test_thirteen_planned_slides_emit_thirteen_card_segments() -> None:
    planned = _deepening_planned_specs(13)
    slots = (
        GammaContentSlot("cover.title", "Demo"),
        GammaContentSlot("cover.client_name", "Acme"),
        GammaContentSlot("executive_summary.body", "Summary"),
        GammaContentSlot("next_steps.body", "Confirm next steps."),
    )
    _, num_cards = build_scratch_input_text(slots, planned_slide_specs=planned)
    assert num_cards == 13


def test_final_next_steps_remains_in_outbound_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_client, "owned_https_prefixes", lambda: (f"{OWNED_BASE}/",))
    planned = _deepening_planned_specs(15)
    payload = _scratch_payload(planned_slide_specs=planned)

    assert payload["numCards"] == 15
    assert "next_steps.body:" in payload["inputText"].split(CARD_BREAK)[-1]


def test_missing_framework_slot_uses_slide_spec_fallback_for_planned_layout() -> None:
    planned = (
        {"layoutId": "COVER_01", "title": "Cover"},
        {"layoutId": "CONTEXT_01", "title": "Context headline", "subtitle": "Context detail"},
        {"layoutId": "NEXT_STEPS_01", **NEXT_STEPS_FIXTURE},
    )
    slots = (
        GammaContentSlot("cover.title", "Demo"),
        GammaContentSlot("cover.client_name", "Acme"),
    )
    aligned = align_slots_with_planned_slides(slots, planned)
    segments = build_card_segments(aligned, planned_slide_specs=planned)
    assert len(segments) == 3
    assert any(slot.name == "context.summary" for slot in aligned)
    assert any(slot.name == "next_steps.body" for slot in aligned)
    assert segments[-1].startswith("next_steps.body:")


def test_template_mode_payload_unchanged_without_card_split() -> None:
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    request = _request()
    payload = client._generation_payload(request)  # noqa: SLF001

    assert client._generation_path(request) == "/v1.0/generations/from-template"  # noqa: SLF001
    assert "cardSplit" not in payload
    assert "numCards" not in payload


def test_logo_header_footer_still_present_on_scratch_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(live_client, "owned_https_prefixes", lambda: (f"{OWNED_BASE}/",))
    payload = _scratch_payload()

    bottom_right = payload["cardOptions"]["headerFooter"]["bottomRight"]
    assert bottom_right["source"] == "custom"
    assert bottom_right["src"]
    assert bottom_right["size"] == "sm"
