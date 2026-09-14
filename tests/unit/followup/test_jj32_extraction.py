"""JJ-32 — transcript → follow-up JSON (Claude mocked)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from services.followup.extraction import (
    ACTION_OVERFLOW_FLAG,
    PROMPT_VERSION,
    FollowupExtractionError,
    extract_followup,
    followup_fixture_names,
    load_followup_fixture,
    resolve_relative_due,
)
from services.observability.llm_logger import (
    STAGE_FOLLOWUP_EXTRACTION,
    clear_generation_jobs,
    jobs_for_opportunity,
)

PROMPTS = Path(__file__).resolve().parents[3] / "apps" / "api" / "llm" / "claude" / "prompts"


def _complete_with(payload: dict):
    def complete(system: str, user: str, schema: dict) -> dict:
        assert PROMPT_VERSION in system
        assert "JSON only" in system
        assert "UNTRUSTED_TRANSCRIPT_BEGIN" in user
        assert schema["required"]
        return deepcopy(payload)

    return complete


def test_prompt_version_matches_prompt_file() -> None:
    first_line = PROMPTS.joinpath("followup_extraction_v1.txt").read_text(encoding="utf-8").splitlines()[0]
    assert PROMPT_VERSION == first_line


@pytest.mark.parametrize("name", followup_fixture_names())
def test_fixture_transcripts_extract_to_frozen_json(name: str) -> None:
    transcript, expected, calendar = load_followup_fixture(name)
    clear_generation_jobs()
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        opportunity_id="OPP-JJ32",
        complete=_complete_with(expected),
    )
    assert result == expected
    assert result["project_name"] is None
    jobs = jobs_for_opportunity("OPP-JJ32", stages=[STAGE_FOLLOWUP_EXTRACTION])
    assert jobs
    assert jobs[0]["prompt_version"] == PROMPT_VERSION
    assert jobs[0]["stage"] == STAGE_FOLLOWUP_EXTRACTION


def test_clear_workshop_has_three_outcomes_and_no_small_talk() -> None:
    transcript, expected, calendar = load_followup_fixture("workshop_clear")
    blob = json.dumps(expected)
    assert len(expected["key_points"]) == 3
    assert all(len(point.split()) <= 20 for point in expected["key_points"])
    assert any(item["action"].startswith("Deliver") for item in expected["action_items"])
    assert {item["owner"] for item in expected["action_items"]} == {"Lena Hoffmann", "Markus Weber"}
    for banned in ("weekend", "football", "canteen", "cake", "coffee"):
        assert banned not in blob.lower()
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(expected),
    )
    assert result["key_points"] == expected["key_points"]
    assert result["action_items"] == expected["action_items"]


def test_unowned_commitment_becomes_open_question() -> None:
    transcript, expected, calendar = load_followup_fixture("unowned_commitment")
    messy = deepcopy(expected)
    messy["action_items"] = [
        {
            "action": "Deliver the interface specification next week",
            "owner": None,
            "due": "TBD",
        }
    ]
    messy["open_questions"] = []
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(messy),
    )
    assert result["action_items"] == []
    assert result["open_questions"]
    assert "interface specification" in result["open_questions"][0].lower()


def test_next_friday_resolves_against_meeting_date() -> None:
    assert resolve_relative_due("next Friday", "11.09.2026") == "18.09.2026"
    transcript, expected, calendar = load_followup_fixture("next_friday")
    messy = deepcopy(expected)
    messy["action_items"][0]["due"] = "next Friday"
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(messy),
    )
    assert result["action_items"][0]["due"] == "18.09.2026"


def test_missing_deadline_is_tbd() -> None:
    transcript, expected, calendar = load_followup_fixture("no_deadline")
    messy = deepcopy(expected)
    messy["action_items"][0]["due"] = None
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(messy),
    )
    assert result["action_items"][0]["due"] == "TBD"
    assert "01." not in result["action_items"][0]["due"]


def test_noisy_speakers_are_low_confidence_with_review_flags() -> None:
    transcript, expected, calendar = load_followup_fixture("noisy_speakers")
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(expected),
    )
    assert result["confidence"]["action_items"] == "low"
    assert result["review_flags"]
    assert "action_items_low_confidence" in result["review_flags"]
    assert result["action_items"] == []


def test_action_overflow_keeps_five_nearest_and_flags() -> None:
    transcript, expected, calendar = load_followup_fixture("action_overflow")
    sixth = {
        "action": "Write the cutover checklist",
        "owner": "Lena Hoffmann",
        "due": "23.09.2026",
    }
    messy = deepcopy(expected)
    messy["action_items"] = [*expected["action_items"], sixth]
    messy["review_flags"] = []
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(messy),
    )
    assert len(result["action_items"]) == 5
    assert result["action_items"][-1]["due"] == "22.09.2026"
    assert all(item["due"] != "23.09.2026" for item in result["action_items"])
    assert ACTION_OVERFLOW_FLAG in result["review_flags"]


def test_invented_decision_date_or_owner_fails() -> None:
    transcript, expected, calendar = load_followup_fixture("workshop_clear")

    invented_decision = deepcopy(expected)
    invented_decision["decisions"] = [*expected["decisions"], "We will acquire SAP"]
    with pytest.raises(FollowupExtractionError, match="invented decision"):
        extract_followup(
            transcript,
            calendar_meeting_date=calendar,
            complete=_complete_with(invented_decision),
        )

    invented_date = deepcopy(expected)
    invented_date["action_items"][0]["due"] = "01.01.2099"
    with pytest.raises(FollowupExtractionError, match="invented date"):
        extract_followup(
            transcript,
            calendar_meeting_date=calendar,
            complete=_complete_with(invented_date),
        )

    invented_owner = deepcopy(expected)
    invented_owner["action_items"][0]["owner"] = "Dr. Invented"
    with pytest.raises(FollowupExtractionError, match="invented owner"):
        extract_followup(
            transcript,
            calendar_meeting_date=calendar,
            complete=_complete_with(invented_owner),
        )


def test_project_name_is_forced_null() -> None:
    transcript, expected, calendar = load_followup_fixture("workshop_clear")
    messy = deepcopy(expected)
    messy["project_name"] = "Guessed Project"
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(messy),
    )
    assert result["project_name"] is None


def test_surplus_key_points_are_dropped() -> None:
    transcript, expected, calendar = load_followup_fixture("workshop_clear")
    messy = deepcopy(expected)
    messy["key_points"] = [
        *expected["key_points"],
        "A fourth outcome must not appear in the JSON",
    ]
    result = extract_followup(
        transcript,
        calendar_meeting_date=calendar,
        complete=_complete_with(messy),
    )
    assert result["key_points"] == expected["key_points"]
    assert len(result["key_points"]) == 3


def test_empty_transcript_is_rejected() -> None:
    with pytest.raises(FollowupExtractionError, match="empty transcript"):
        extract_followup("  ", complete=_complete_with({}))
