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
    assert summary["executive_summary"] == "Automate invoice matching with human control."
    assert summary["key_requirements"]
    assert summary["target_outcomes"]
    assert summary["assumptions"]
    assert summary["readiness"]["build_readiness"] == 58
    for field in (
        "executive_summary",
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
