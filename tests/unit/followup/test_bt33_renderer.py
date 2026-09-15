"""BT-33 follow-up renderer unit tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.followup.errors import FollowupRenderError
from services.followup.extraction import load_followup_fixture
from services.followup.rendering import (
    ACTION_OVERFLOW_FLAG,
    KEY_POINTS_OVERFLOW_FLAG,
    MAX_BODY_WORDS,
    _body_word_count,
    render_followup_draft,
)

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures" / "followup_extraction"
BT33_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "followup_render"


def _load_json(name: str, *, bt_owned: bool = False) -> dict:
    root = BT33_FIXTURE_DIR if bt_owned else FIXTURE_DIR
    return json.loads((root / name).read_text(encoding="utf-8"))


def _standard_statics(**overrides: object) -> dict:
    base = {
        "project_name": "Acme Invoice Automation",
        "salutation_style": "informal",
        "recipient_first_name": "Markus",
        "time_reference": "today",
        "sender_name": "Lena Hoffmann",
        "sender_role": "Delivery Lead",
    }
    base.update(overrides)
    return base


def test_standard_fixture_renders_subject_body_and_actions() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    draft = render_followup_draft(extraction, _standard_statics())
    assert draft["subject"] == "Acme Invoice Automation — Follow-up Requirements Workshop (11.09.2026)"
    assert "Interface will be REST, not SOAP" in draft["body"]
    assert "Provide test invoices — Markus Weber, by 18.09.2026" in draft["body"]
    assert "Deliver interface specification — Lena Hoffmann, by 25.09.2026" in draft["body"]
    assert draft["status"] == "draft"
    assert draft["review_flags"] == []


def test_empty_open_questions_omits_block() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    draft = render_followup_draft(extraction, _standard_statics())
    assert "Open from our side" not in draft["body"]


def test_empty_action_items_uses_no_actions_fallback() -> None:
    extraction = _load_json("workshop_clear.json")
    extraction["action_items"] = []
    draft = render_followup_draft(
        extraction,
        _standard_statics(no_actions_dependency="the sandbox access"),
    )
    assert "Next steps" not in draft["body"]
    assert (
        "No action items from our side for now — we will come back to you once "
        "the sandbox access is clarified."
    ) in draft["body"]


def test_tbd_renders_as_date_to_be_confirmed_and_sorts_last() -> None:
    _, extraction, _ = load_followup_fixture("no_deadline")
    extraction["action_items"].append(
        {
            "action": "Deliver interface specification",
            "owner": "Lena Hoffmann",
            "due": "18.09.2026",
        }
    )
    draft = render_followup_draft(extraction, _standard_statics())
    tbd_index = draft["body"].index("date to be confirmed")
    dated_index = draft["body"].index("18.09.2026")
    assert dated_index < tbd_index


def test_action_items_sorted_by_due_date_ascending() -> None:
    extraction = _load_json("workshop_clear.json")
    extraction["action_items"] = [
        {"action": "Book the UAT window", "owner": "Markus Weber", "due": "22.09.2026"},
        {"action": "Provide test invoices", "owner": "Markus Weber", "due": "18.09.2026"},
        {"action": "Deliver interface specification", "owner": "Lena Hoffmann", "due": "25.09.2026"},
    ]
    draft = render_followup_draft(extraction, _standard_statics())
    pos_18 = draft["body"].index("18.09.2026")
    pos_22 = draft["body"].index("22.09.2026")
    pos_25 = draft["body"].index("25.09.2026")
    assert pos_18 < pos_22 < pos_25


def test_key_points_overflow_adds_protocol_reference() -> None:
    extraction = _load_json("workshop_clear.json")
    extraction["review_flags"] = [KEY_POINTS_OVERFLOW_FLAG]
    draft = render_followup_draft(
        extraction,
        _standard_statics(),
        attachment_name="Meeting protocol.pdf",
    )
    assert "Further detail is in the attached protocol." in draft["body"]


def test_action_overflow_adds_protocol_reference() -> None:
    _, extraction, _ = load_followup_fixture("action_overflow")
    draft = render_followup_draft(
        extraction,
        _standard_statics(),
        attachment_name="Meeting protocol.pdf",
    )
    assert "Further detail is in the attached protocol." in draft["body"]
    assert draft["body"].count("Provide test invoices") == 1


def test_formal_client_uses_formal_greeting() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    draft = render_followup_draft(
        extraction,
        _standard_statics(
            salutation_style="formal",
            salutation="Mr",
            last_name="Weber",
        ),
    )
    assert draft["body"].startswith("Dear Mr Weber,")


def test_next_meeting_included_only_when_present() -> None:
    extraction = _load_json("workshop_clear.json")
    without = render_followup_draft(extraction, _standard_statics())
    assert "Next session:" not in without["body"]

    extraction["next_meeting"] = {"date": "25.09.2026", "time": "10:00 CET"}
    with_meeting = render_followup_draft(extraction, _standard_statics())
    assert "Next session: 25.09.2026, 10:00 CET." in with_meeting["body"]


def test_decision_block_included_only_when_present() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    draft = render_followup_draft(extraction, _standard_statics())
    assert "Decisions" in draft["body"]
    assert "REST is the agreed interface (agreed 11.09.2026)" in draft["body"]

    extraction["decisions"] = []
    without = render_followup_draft(extraction, _standard_statics())
    assert "Decisions" not in without["body"]


def test_leftover_placeholders_fail_closed() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    with pytest.raises(FollowupRenderError) as exc:
        render_followup_draft(
            extraction,
            _standard_statics(project_name="{{project_name}}"),
        )
    assert exc.value.code == "FOLLOWUP_PLACEHOLDER_LEFTOVER"


def test_body_within_word_limit_passes() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    draft = render_followup_draft(extraction, _standard_statics())
    greeting = "Hi Markus,"
    signature = "Best regards\nLena Hoffmann\nDelivery Lead · BOREK"
    assert _body_word_count(draft["body"], greeting, signature) <= MAX_BODY_WORDS


def test_body_over_word_limit_fails_after_omissions() -> None:
    extraction = _load_json("word_limit_overflow.json", bt_owned=True)
    with pytest.raises(FollowupRenderError) as exc:
        render_followup_draft(extraction, _standard_statics())
    assert exc.value.code == "FOLLOWUP_BODY_WORD_LIMIT"


def test_rendered_content_uses_only_input_and_statics() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    statics = _standard_statics()
    draft = render_followup_draft(extraction, statics)
    for point in extraction["key_points"]:
        assert point in draft["body"]
    for item in extraction["action_items"]:
        assert str(item["action"]) in draft["body"]
        assert str(item["owner"]) in draft["body"]
    assert statics["sender_name"] in draft["body"]
    assert "invented sentence" not in draft["body"].lower()


def test_renderer_does_not_mutate_extraction_json() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    before = copy.deepcopy(extraction)
    render_followup_draft(extraction, _standard_statics())
    assert extraction == before


def test_client_addressed_before_review_fails_closed() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    with pytest.raises(FollowupRenderError) as exc:
        render_followup_draft(
            extraction,
            _standard_statics(),
            client_addressed=True,
            reviewed=False,
        )
    assert exc.value.code == "FOLLOWUP_CLIENT_UNREVIEWED"


def test_invalid_extraction_schema_fails_closed() -> None:
    _, extraction, _ = load_followup_fixture("workshop_clear")
    extraction["meeting_date"] = "2026-09-11"
    with pytest.raises(Exception):
        render_followup_draft(extraction, _standard_statics())
