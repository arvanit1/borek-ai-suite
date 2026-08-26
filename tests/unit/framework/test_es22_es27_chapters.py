"""ES-22 … ES-27 — chapters 8–13 acceptance."""

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


def test_es22_security_has_guardrails_breach_and_no_employee_evaluation() -> None:
    chapter = _framework()["chapters"][8]
    blob = str(chapter["body"]).lower()
    assert any(block.get("block") == "kv_rows" for block in chapter["body"])
    for token in ("classification", "residency", "audit", "human"):
        assert token in blob
    assert "employee" in blob
    assert "breach" in blob
    assert "acceptance" in blob


def test_es23_roi_has_table_qualitative_and_three_point_sensitivity() -> None:
    chapter = _framework()["chapters"][9]
    assert any(block.get("block") == "table" for block in chapter["body"])
    assert any(block.get("block") == "bullets" for block in chapter["body"])
    sensitivities = [block for block in chapter["body"] if block.get("block") == "sensitivity"]
    assert len(sensitivities[0]["rows"]) == 3
    assert "payback" in str(chapter["body"]).lower()


def test_es24_effort_has_tier_drivers_range_team_and_ch12_alignment() -> None:
    chapter = _framework()["chapters"][10]
    blob = str(chapter["body"]).lower()
    assert "tier" in blob
    assert "driver" in blob
    assert "min" in blob and "likely" in blob and "max" in blob
    assert "confidence" in blob
    assert "team" in blob
    assert any(block.get("block") == "timeline" for block in chapter["body"])
    assert "chapter 12" in blob


def test_es25_gates_have_three_scores_open_items_and_nothing_guessed() -> None:
    chapter = _framework()["chapters"][11]
    bars = [block for block in chapter["body"] if block.get("block") == "score_bars"]
    assert len(bars[0]["items"]) == 3
    assert all(item.get("explanation") for item in bars[0]["items"])
    assert any(block.get("block") == "table" for block in chapter["body"])
    assert "guess" in str(chapter["body"]).lower()


def test_es26_evolution_is_today_assistive_hitl_proposal_only() -> None:
    framework = _framework()
    chapter = framework["chapters"][12]
    blob = str(chapter["body"]).lower()
    assert any(block.get("block") == "table" for block in chapter["body"])
    assert "today" in blob
    assert "assistive" in blob
    assert "hitl" in blob
    assert "proposal" in blob
    stages = framework["evolution_stages"]
    assert len(stages) == 4
    assert stages[2]["recommended"] is True


def test_es27_next_steps_are_numbered_with_who_when_and_glossary() -> None:
    chapter = _framework()["chapters"][13]
    tables = [block for block in chapter["body"] if block.get("block") == "table"]
    columns = " ".join(str(col) for col in tables[0]["columns"]).lower()
    assert "who" in columns
    assert "when" in columns
    glossaries = [block for block in chapter["body"] if block.get("block") == "glossary"]
    assert glossaries[0]["terms"]


def test_es22_rejects_missing_employee_guardrail() -> None:
    framework = _framework()
    framework["chapters"][8]["body"] = [
        {
            "block": "kv_rows",
            "caption": "Binding guardrails",
            "rows": [
                {"label": "Data classification", "value": "named"},
                {"label": "Data residency", "value": "named"},
                {"label": "Audit", "value": "named"},
                {"label": "Human control", "value": "named"},
                {"label": "Breach", "value": "A breach is a failed acceptance test."},
            ],
        }
    ]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "employees" in exc_info.value.user_message


def test_es26_rejects_missing_evolution_table() -> None:
    framework = _framework()
    framework["chapters"][12]["body"] = [{"block": "prose", "text": "Stages exist."}]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "ladder" in exc_info.value.user_message
