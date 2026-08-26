"""JJ-11..JJ-13: Group B business rules run before rendering."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.business_rules import (
    GroupBBusinessRuleError,
    validate_group_b_business_rules,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_jj11_valid_timeline_dates_pass() -> None:
    validate_group_b_business_rules(_load("timeline_01.realistic.json"))


def test_jj11_end_before_start_fails() -> None:
    payload = _load("timeline_01.realistic.json")
    payload["milestones"][0]["date"] = "Week 14"
    payload["milestones"][-1]["date"] = "Week 2"

    with pytest.raises(GroupBBusinessRuleError, match="end must be on or after"):
        validate_group_b_business_rules(payload)


def test_jj11_iso_date_range_end_before_start_fails() -> None:
    payload = _load("timeline_01.minimal.json")
    payload["milestones"][0]["date"] = "2026-12-01 to 2026-01-15"

    with pytest.raises(GroupBBusinessRuleError, match="end before start"):
        validate_group_b_business_rules(payload)


def test_jj12_valid_team_fte_passes() -> None:
    validate_group_b_business_rules(_load("team_fte_01.realistic.json"))


def test_jj12_negative_role_fte_fails() -> None:
    payload = _load("team_fte_01.minimal.json")
    payload["roles"][0]["fte"] = "-1"

    with pytest.raises(GroupBBusinessRuleError, match="must not be negative"):
        validate_group_b_business_rules(payload)


def test_jj12_unicode_minus_fte_fails() -> None:
    payload = _load("team_fte_01.minimal.json")
    payload["roles"][0]["fte"] = "−0.5"

    with pytest.raises(GroupBBusinessRuleError, match="must not be negative"):
        validate_group_b_business_rules(payload)


def test_jj12_range_display_is_not_treated_as_negative() -> None:
    payload = _load("team_fte_01.minimal.json")
    payload["roles"][0]["fte"] = "1–2"
    validate_group_b_business_rules(payload)


def test_jj13_duplicate_timeline_milestone_ids_fail() -> None:
    payload = copy.deepcopy(_load("timeline_01.realistic.json"))
    payload["milestones"][2]["id"] = payload["milestones"][0]["id"]

    with pytest.raises(GroupBBusinessRuleError, match="must not share an id"):
        validate_group_b_business_rules(payload)


def test_jj13_duplicate_standalone_milestone_names_fail() -> None:
    payload = copy.deepcopy(_load("milestones_01.realistic.json"))
    payload["milestones"][1]["name"] = payload["milestones"][0]["name"]

    with pytest.raises(GroupBBusinessRuleError, match="must not share an id"):
        validate_group_b_business_rules(payload)


def test_process_flow_has_no_group_b_business_rule_surface() -> None:
    validate_group_b_business_rules(_load("process_flow_01.realistic.json"))
