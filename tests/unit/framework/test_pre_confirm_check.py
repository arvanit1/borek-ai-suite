"""ES-13 — contradictory chapter-6 AI split cannot reach confirmed."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.framework.pipeline import generate_customer_framework
from services.framework.pre_confirm_check import (
    PreConfirmError,
    confirm_customer_report,
    prepare_framework_for_confirm,
    pre_confirm_check,
    scrub_ai_split_echoes,
)

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


def _framework() -> dict:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    return generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )


def _ai_split(framework: dict) -> dict:
    for block in framework["chapters"][6]["body"]:
        if isinstance(block, dict) and block.get("block") == "ai_split":
            return block
    raise AssertionError("chapter 6 is missing ai_split")


def test_golden_draft_can_be_confirmed() -> None:
    original = _framework()
    snapshot = copy.deepcopy(original)
    confirmed = confirm_customer_report(
        original, now=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc)
    )
    assert original == snapshot
    assert original["status"] == "draft"
    assert confirmed["status"] == "confirmed"
    assert confirmed["change_log"][-1] == "Customer report confirmed"


def test_used_and_not_used_overlap_blocks_confirm() -> None:
    framework = _framework()
    split = _ai_split(framework)
    split["used_for"] = ["Deciding whether a case matches"]
    split["not_used_for"] = ["Deciding whether a case matches", "Evaluating employees"]
    with pytest.raises(PreConfirmError) as exc_info:
        confirm_customer_report(framework)
    assert framework["status"] == "draft"
    assert "contradicts" in exc_info.value.user_message.lower()


def test_other_chapter_contradiction_blocks_confirm() -> None:
    framework = _framework()
    framework["chapters"][5]["body"].append(
        {
            "block": "prose",
            "text": "The agent decides whether a case matches and posts without a person.",
        }
    )
    with pytest.raises(PreConfirmError) as exc_info:
        pre_confirm_check(framework)
    assert "another chapter" in exc_info.value.user_message.lower()


def test_contradictory_draft_can_still_be_generated() -> None:
    framework = _framework()
    split = _ai_split(framework)
    split["used_for"] = ["Deciding whether a case matches"]
    split["not_used_for"] = ["Deciding whether a case matches"]
    assert framework["status"] == "draft"
    with pytest.raises(PreConfirmError):
        confirm_customer_report(framework)


def test_agreeing_ai_echo_outside_chapter_6_is_scrubbed_before_confirm() -> None:
    framework = _framework()
    framework["chapters"][8]["body"].append(
        {
            "block": "prose",
            "text": "The agent does not assess any employee. Human control stays with managers.",
        }
    )
    prepare_framework_for_confirm(framework)
    pre_confirm_check(framework)
    confirmed = confirm_customer_report(framework)
    assert confirmed["status"] == "confirmed"


def test_chapter_5_never_autonomous_survives_confirm_prepare() -> None:
    framework = _framework()
    split = _ai_split(framework)
    split["not_used_for"] = list(split.get("not_used_for") or []) + [
        "Acting on its own toward counterparties"
    ]
    framework["chapters"][5]["body"] = [
        {
            "block": "callout",
            "kind": "important",
            "text": "In no exception does the agent act on its own toward counterparties. People decide.",
        }
    ]
    prepare_framework_for_confirm(framework)
    blob = str(framework["chapters"][5]["body"]).lower()
    assert "on its own" in blob or "people decide" in blob


def test_real_contradiction_still_blocks_confirm_after_scrub() -> None:
    framework = _framework()
    framework["chapters"][5]["body"].append(
        {
            "block": "prose",
            "text": "The agent decides whether a case matches and posts without a person.",
        }
    )
    prepare_framework_for_confirm(framework)
    with pytest.raises(PreConfirmError) as exc_info:
        confirm_customer_report(framework)
    assert "another chapter" in exc_info.value.user_message.lower()


def test_hitl_approval_wording_is_neutralized_for_confirm() -> None:
    framework = _framework()
    split = _ai_split(framework)
    split["not_used_for"] = list(split.get("not_used_for") or []) + [
        "Final approval authority on any requisition",
        "Approving exceptions – all exceptions go to people",
    ]
    framework["chapters"][4]["body"].append(
        {
            "block": "prose",
            "text": (
                "At stage 2, the agent monitors Teams channels and posts approvals after rules match; "
                "exceptions go to the buyer queue."
            ),
        }
    )
    prepare_framework_for_confirm(framework)
    pre_confirm_check(framework)
    appended = framework["chapters"][4]["body"][-1]
    prose = str(appended).lower()
    assert "the agent" not in prose or "the workflow" in prose


def test_human_exception_routing_does_not_contradict_chapter_6() -> None:
    """ES-13: a human gate and routed exceptions are not autonomous AI use."""
    framework = _framework()
    split = _ai_split(framework)
    split["used_for"] = list(split.get("used_for") or []) + [
        "Post approval automatically when total is at most EUR 10,000 and no exceptions are present."
    ]
    split["not_used_for"] = list(split.get("not_used_for") or []) + [
        "Deciding on split deliveries (always route to category manager).",
        "One-click manager approval for requests above EUR 10,000 (human gate).",
    ]
    framework["chapters"][4]["body"].append(
        {
            "block": "prose",
            "text": (
                "The workflow posts approval automatically up to EUR 10,000 when there is no exception. "
                "Requests above the threshold go to the manager; split deliveries go to the category manager."
            ),
        }
    )

    prepare_framework_for_confirm(framework)
    pre_confirm_check(framework)
