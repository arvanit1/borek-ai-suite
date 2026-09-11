"""ES-36/ES-37/ES-38 — review summary, attention signals, and Word export."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.framework.pre_confirm_check import PreConfirmError
from services.framework.rendering.customer_docx import render_customer_docx
from services.framework.review_insights import (
    REVIEW_STATE_BLOCKING,
    REVIEW_STATE_MISSING,
    REVIEW_STATE_READY,
    REVIEW_STATE_RECOMMENDED,
    REVIEW_STATE_WEAK_EVIDENCE,
    attach_review_insights,
    build_attention_bundle,
    build_review_summary,
)

FIXTURE = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures" / "framework_object.minimal.json"


def _framework(**overrides: object) -> dict:
    framework = json.loads(FIXTURE.read_text(encoding="utf-8"))
    framework.update(overrides)
    return framework


def test_es36_review_summary_contains_required_fields() -> None:
    framework = attach_review_insights(
        _framework(
            render={"allowed": True, "assumptions_banner": False, "band": "ready_to_build"},
            readiness_band="ready_to_build",
            open_items=[{"item_type": "assumption", "description": "Hours validated in workshop"}],
            kpis=[{"name": "Processing time", "target": "Under 2 days"}],
            access_needs=[{"category": "ERP access", "specifically": "Read-only AP role"}],
            chapters=[
                {
                    "chapter_id": "1",
                    "title": "Management summary",
                    "body": [{"summary": "Automate invoice matching with human control."}],
                    "source_refs": [{"conversation_id": "C1", "excerpt_pointer": "turn:1"}],
                }
            ]
            + _framework()["chapters"][2:],
        )
    )
    summary = framework["review_summary"]
    assert summary["executive_summary_points"][0] == "Automate invoice matching with human control."
    assert len(summary["executive_summary_points"]) >= 3
    assert summary["executive_summary"].startswith("Automate invoice matching with human control.")
    assert summary["key_requirements"]
    assert summary["target_outcomes"]
    assert summary["assumptions"]
    assert summary["readiness"]["build_readiness"] == 58
    for field in (
        "executive_summary",
        "executive_summary_points",
        "key_pain_points",
        "key_requirements",
        "target_outcomes",
        "assumptions",
        "open_questions",
        "contradictions",
        "evidence_warnings",
        "readiness",
        "blocking_items",
        "confirm_ready",
        "headline",
        "language",
    ):
        assert field in summary
    blob = json.dumps(summary)
    assert "never mentioned in the source" not in blob


def test_es37_attention_states_cover_blocking_contradiction() -> None:
    framework = _framework()
    chapter_6 = next(ch for ch in framework["chapters"] if ch["chapter_id"] == "6")
    chapter_6["body"] = [
        {
            "block": "ai_split",
            "used_for": ["Deciding whether a case matches"],
            "not_used_for": ["Deciding whether a case matches"],
        }
    ]
    bundle = build_attention_bundle(framework)
    assert bundle["review_state"] == REVIEW_STATE_BLOCKING
    assert any(signal["id"] == REVIEW_STATE_BLOCKING for signal in bundle["signals"])


def test_es37_attention_state_missing_required_information() -> None:
    framework = _framework(
        render={"allowed": False, "band": "not_ready", "reason": "Build-readiness is 58/100."},
    )
    bundle = build_attention_bundle(framework)
    assert bundle["review_state"] in {REVIEW_STATE_MISSING, REVIEW_STATE_WEAK_EVIDENCE}
    assert any(signal["id"] == REVIEW_STATE_MISSING for signal in bundle["signals"])


def test_es37_attention_state_weak_evidence() -> None:
    framework = _framework(
        render={"allowed": True, "assumptions_banner": True, "band": "ready_with_assumptions"},
    )
    bundle = build_attention_bundle(framework)
    assert any(signal["id"] == REVIEW_STATE_WEAK_EVIDENCE for signal in bundle["signals"])


def test_es37_ready_to_approve_when_no_blockers() -> None:
    framework = attach_review_insights(
        _framework(
            render={"allowed": True, "assumptions_banner": False, "band": "ready_to_build"},
            readiness_band="ready_to_build",
            quality_scores={
                "opportunity_rating": 80,
                "conversation_quality": 75,
                "build_readiness": 85,
                "rationale": {},
            },
            chapters=[
                {
                    "chapter_id": str(index),
                    "title": f"Chapter {index}",
                    "body": [{"summary": "Grounded fact."}] if index == 1 else [],
                    "source_refs": [{"conversation_id": "C1", "excerpt_pointer": f"turn:{index}"}]
                    if index not in {"0", "13"}
                    else [],
                }
                for index in range(14)
            ],
        )
    )
    chapter_6 = next(ch for ch in framework["chapters"] if ch["chapter_id"] == "6")
    chapter_6["body"] = [
        {
            "block": "ai_split",
            "used_for": ["Reading documents into structured fields"],
            "not_used_for": ["Deciding whether a case matches"],
        }
    ]
    framework = attach_review_insights(framework)
    assert framework["attention"]["review_state"] == REVIEW_STATE_READY


def test_es37_high_scores_cannot_hide_blocking_contradiction() -> None:
    framework = _framework(
        render={"allowed": True, "assumptions_banner": False, "band": "ready_to_build"},
        readiness_band="ready_to_build",
        quality_scores={
            "opportunity_rating": 95,
            "conversation_quality": 92,
            "build_readiness": 94,
            "rationale": {},
        },
    )
    chapter_6 = next(ch for ch in framework["chapters"] if ch["chapter_id"] == "6")
    chapter_6["body"] = [
        {
            "block": "ai_split",
            "used_for": ["Deciding whether a case matches"],
            "not_used_for": ["Deciding whether a case matches"],
        }
    ]
    bundle = build_attention_bundle(framework)
    assert bundle["review_state"] == REVIEW_STATE_BLOCKING
    assert any(signal["id"] == REVIEW_STATE_BLOCKING for signal in bundle["signals"])


def test_attach_review_insights_adds_observability_and_pii_meta() -> None:
    framework = attach_review_insights(
        _framework(
            generation_meta={
                "llm_used": True,
                "llm_model": "claude-test",
                "prompt_version": "synthesis_v1",
                "llm_job_log": [
                    {
                        "stage": "framework_synthesis",
                        "model": "claude-test",
                        "prompt_version": "synthesis_v1",
                        "input_tokens": 500,
                        "output_tokens": 700,
                    }
                ],
            }
        ),
        pii_redaction_enabled=False,
    )
    assert framework["review_summary"]["headline"] == "Invoice 3-Way Match Automation"
    assert framework["attention"]["signals"]
    assert framework["generation_meta"]["pii_handling"]["redaction_enabled"] is False


def test_es36_review_summary_respects_framework_language() -> None:
    framework = _framework(language="de", language_master="de")
    framework["customer_view"] = {
        "render_language": "de",
        "title": framework["title"],
        "department": framework["department"],
        "chapters": [],
    }
    summary = build_review_summary(framework)
    assert summary["language"] == "de"


def test_executive_summary_is_at_least_three_bullet_points() -> None:
    summary = build_review_summary(
        _framework(
            render={"allowed": True, "assumptions_banner": False, "band": "ready_to_build"},
            kpis=[{"name": "Processing time", "target": "Under 2 days"}],
            access_needs=[{"category": "ERP access", "specifically": "Read-only AP role"}],
            chapters=[
                {
                    "chapter_id": "1",
                    "title": "Management summary",
                    "body": [
                        {
                            "summary": (
                                "Accounts Payable matches around 3,000 invoices per month. "
                                "Matching is still done by hand against purchase orders. "
                                "The team wants automation with human control."
                            )
                        }
                    ],
                    "source_refs": [{"conversation_id": "C1", "excerpt_pointer": "turn:1"}],
                }
            ]
            + _framework()["chapters"][2:],
        )
    )
    points = summary["executive_summary_points"]
    assert len(points) >= 3
    assert points[0].startswith("Accounts Payable matches around 3,000 invoices per month")
    assert all(isinstance(point, str) and point.strip() for point in points)


def test_docx_export_renders_zip_magic_bytes() -> None:
    base = _framework(
        render={"allowed": True, "assumptions_banner": True, "band": "ready_with_assumptions"},
    )
    base["customer_view"] = {
        "title": base["title"],
        "department": base["department"],
        "opportunity_id": base["opportunity_id"],
        "chapters": [
            {
                "chapter_id": "1",
                "title": "Management summary",
                "body": "Automate invoice matching.",
            }
        ],
    }
    framework = attach_review_insights(base)
    docx_bytes = render_customer_docx(framework)
    assert docx_bytes.startswith(b"PK")


def test_docx_export_blocked_when_render_not_allowed() -> None:
    framework = _framework(render={"allowed": False, "band": "not_ready", "reason": "Too low."})
    with pytest.raises(Exception):
        render_customer_docx(framework)


def _sourced_chapters_with_ai_split() -> list[dict]:
    chapters = [
        {
            "chapter_id": str(index),
            "title": f"Chapter {index}",
            "body": [{"block": "prose", "text": "Grounded fact.", "source_refs": [{"conversation_id": "C1", "excerpt_pointer": f"turn:{index}"}]}]
            if index != 6
            else [
                {
                    "block": "ai_split",
                    "used_for": ["Reading documents into structured fields"],
                    "not_used_for": ["Deciding whether a case matches"],
                    "source_refs": [{"conversation_id": "C1", "excerpt_pointer": "turn:6"}],
                }
            ],
            "source_refs": [{"conversation_id": "C1", "excerpt_pointer": f"turn:{index}"}]
            if index not in {0, 13}
            else [],
        }
        for index in range(14)
    ]
    return chapters


def test_es37_low_build_readiness_does_not_block_presentation_approval() -> None:
    framework = _framework(
        render={
            "allowed": False,
            "band": "not_ready",
            "reason": "Build-readiness is 58/100. A customer report is not rendered below 60. Close the gaps first.",
        },
        quality_scores={
            "opportunity_rating": 72,
            "conversation_quality": 65,
            "build_readiness": 58,
            "rationale": {},
        },
        chapters=_sourced_chapters_with_ai_split(),
        open_items=[{"item_type": "assumption", "description": "Hours validated in workshop", "owner": "Business", "consequence_if_different": "Confirm."}],
    )
    bundle = build_attention_bundle(framework)
    summary = build_review_summary(framework)
    assert all(signal.get("severity") != "blocking" for signal in bundle["signals"])
    assert bundle["review_state"] == REVIEW_STATE_RECOMMENDED
    assert summary["confirm_ready"] is True
    assert not any(item.get("kind") == "readiness" for item in summary["blocking_items"])
    assert any("customer report" in (signal.get("action") or "").lower() for signal in bundle["signals"])
    assert not any("close the open items in chapter 11" in (signal.get("action") or "").lower() for signal in bundle["signals"])


def test_es37_three_plus_chapters_without_sources_are_warning_not_blocking() -> None:
    chapters = _sourced_chapters_with_ai_split()
    for chapter in chapters:
        if str(chapter["chapter_id"]) in {"2", "3", "4", "5"}:
            chapter["source_refs"] = []
            chapter["body"] = [{"block": "prose", "text": "Ungrounded derived text."}]
    framework = _framework(
        render={"allowed": True, "assumptions_banner": False, "band": "ready_to_build"},
        chapters=chapters,
    )
    bundle = build_attention_bundle(framework)
    weak = [signal for signal in bundle["signals"] if signal["id"] == REVIEW_STATE_WEAK_EVIDENCE]
    assert weak
    assert all(signal["severity"] == "warning" for signal in weak)
    assert bundle["review_state"] != REVIEW_STATE_BLOCKING
    assert all(signal.get("severity") != "blocking" for signal in bundle["signals"])


def test_es37_three_plus_open_questions_are_warning_not_blocking() -> None:
    framework = _framework(
        render={"allowed": True, "assumptions_banner": False, "band": "ready_to_build"},
        chapters=_sourced_chapters_with_ai_split(),
        open_items=[
            {"item_type": "dependency", "description": f"How to measure outcome {index}?", "owner": "Client", "consequence_if_different": "Ask the client."}
            for index in range(4)
        ],
    )
    bundle = build_attention_bundle(framework)
    missing = [signal for signal in bundle["signals"] if signal["id"] == REVIEW_STATE_MISSING]
    assert missing
    assert all(signal["severity"] == "warning" for signal in missing)
    assert all(signal.get("severity") != "blocking" for signal in bundle["signals"])
    assert bundle["review_state"] == REVIEW_STATE_RECOMMENDED
