"""ES-14, ES-15, ES-16 — chapter 0 / 1 / 2 acceptance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.chapter_validators import validate_all_chapters
from services.framework.chapter_validators.base import ChapterValidationError
from services.framework.pipeline import generate_customer_framework

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


def test_es14_about_has_eight_questions_and_generated_confirmed() -> None:
    chapter = _framework()["chapters"][0]
    blob = str(chapter["body"]).lower()
    bullets = [block for block in chapter["body"] if block.get("block") == "bullets"]
    assert len(bullets[0]["items"]) == 8
    assert "what is it" in blob
    assert "generated" in blob
    assert "human-confirmed" in blob
    assert "traceable" in blob
    assert "ranges" in blob
    assert "false precision" in blob


def test_es15_summary_has_glance_hitl_and_staged_recommendation() -> None:
    chapter = _framework()["chapters"][1]
    blob = str(chapter["body"]).lower()
    assert any(block.get("block") == "prose" for block in chapter["body"])
    assert any(block.get("block") == "kv_rows" for block in chapter["body"])
    assert "human in the loop" in blob
    rec = " ".join(
        str(block.get("text", "")) for block in chapter["body"] if block.get("block") == "callout"
    ).lower()
    assert "stage" in rec
    assert "chapter 11" in rec


def test_es15_rejects_missing_recommendation() -> None:
    framework = _framework()
    framework["chapters"][1]["body"] = [
        {"block": "prose", "text": "Invoice matching is a repeatable task with named volume and cost."},
        {
            "block": "kv_rows",
            "caption": "At a glance",
            "rows": [
                {"label": "Volume", "value": "named"},
                {"label": "Human in the loop", "value": "exceptions stay with people"},
            ],
        },
    ]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "recommendation" in exc_info.value.user_message


def test_es16_as_is_uses_typed_steps_and_cost_table() -> None:
    chapter = _framework()["chapters"][2]
    flows = [block for block in chapter["body"] if block.get("block") == "process_flow"]
    assert flows
    kinds = {node.get("kind") for node in flows[0]["nodes"]}
    assert kinds <= {"agent", "human", "system", "decision", "start_end"}
    assert len(flows[0]["nodes"]) >= 2
    assert any(block.get("block") == "kv_rows" for block in chapter["body"])


def test_es14_rejects_missing_decision_questions() -> None:
    framework = _framework()
    framework["chapters"][0]["body"] = [{"block": "prose", "text": "A generated, human-confirmed report with ranges and traceable numbers, never false precision."}]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "decision_questions" in exc_info.value.user_message


def test_es16_rejects_prose_only_as_is() -> None:
    framework = _framework()
    framework["chapters"][2]["body"] = [{"block": "prose", "text": "People match invoices by hand today."}]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "as_is_flow" in exc_info.value.user_message
