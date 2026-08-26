"""ES-17, ES-18, ES-19, ES-20, ES-21 — chapters 3–7 acceptance."""

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


def test_es17_aim_has_kpi_table_and_conservative_derivation() -> None:
    chapter = _framework()["chapters"][3]
    blob = str(chapter["body"]).lower()
    tables = [block for block in chapter["body"] if block.get("block") == "table"]
    assert tables
    assert "baseline" in str(tables).lower()
    assert "target" in str(tables).lower()
    assert "measured" in str(tables).lower()
    assert "conservative" in blob


def test_es18_to_be_uses_typed_stage_flow_and_today_vs_agent() -> None:
    chapter = _framework()["chapters"][4]
    flows = [block for block in chapter["body"] if block.get("block") == "process_flow"]
    assert flows
    kinds = {node.get("kind") for node in flows[0]["nodes"]}
    assert kinds <= {"agent", "human", "system", "decision", "start_end"}
    assert "stage" in str(chapter["body"]).lower()
    tables = [block for block in chapter["body"] if block.get("block") == "table"]
    assert "today" in str(tables).lower()
    assert "agent" in str(tables).lower()


def test_es19_detail_has_trigger_rules_exceptions_and_never_autonomous() -> None:
    chapter = _framework()["chapters"][5]
    blob = str(chapter["body"]).lower()
    labels = " ".join(
        str(row.get("label", ""))
        for block in chapter["body"]
        if block.get("block") == "kv_rows"
        for row in (block.get("rows") or [])
    ).lower()
    assert "trigger" in labels
    assert "input" in labels
    assert "result" in labels
    assert any(block.get("block") == "table" for block in chapter["body"])
    assert "exception" in blob
    assert "on its own" in blob or "team decides" in blob


def test_es20_built_has_systems_building_blocks_and_ai_split() -> None:
    chapter = _framework()["chapters"][6]
    tables = [block for block in chapter["body"] if block.get("block") == "table"]
    assert any("system" in str(block).lower() for block in tables)
    assert any("building block" in str(block.get("caption", "")).lower() for block in tables)
    splits = [block for block in chapter["body"] if block.get("block") == "ai_split"]
    assert splits
    assert splits[0].get("used_for")
    assert splits[0].get("not_used_for")


def test_es21_client_needs_table_has_status_owner_and_hours() -> None:
    chapter = _framework()["chapters"][7]
    tables = [block for block in chapter["body"] if block.get("block") == "table"]
    assert tables
    columns = " ".join(str(col) for col in tables[0].get("columns") or []).lower()
    assert "status" in columns
    assert "owner" in columns
    assert "hour" in columns


def test_es17_rejects_missing_conservative_kpi_table() -> None:
    framework = _framework()
    framework["chapters"][3]["body"] = [{"block": "prose", "text": "The aim is a measurable state."}]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "kpi_table" in exc_info.value.user_message or "conservative" in exc_info.value.user_message


def test_es18_rejects_prose_only_to_be() -> None:
    framework = _framework()
    framework["chapters"][4]["body"] = [{"block": "prose", "text": "The agent will help at stage 2."}]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "to_be_flow" in exc_info.value.user_message


def test_es19_rejects_missing_trigger_inputs_result() -> None:
    framework = _framework()
    framework["chapters"][5]["body"] = [
        {"block": "prose", "text": "Rules come from the conversations. The team decides; the agent never acts on its own."},
        {"block": "table", "caption": "Rules", "columns": ["Rule"], "rows": [["named"]]},
        {"block": "table", "caption": "Exceptions", "columns": ["Exception"], "rows": [["named"]]},
    ]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "trigger_inputs_result" in exc_info.value.user_message


def test_es20_rejects_missing_building_blocks() -> None:
    framework = _framework()
    framework["chapters"][6]["body"] = [
        block
        for block in framework["chapters"][6]["body"]
        if not (isinstance(block, dict) and block.get("block") == "table" and "building" in str(block.get("caption", "")).lower())
    ]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "building_blocks" in exc_info.value.user_message


def test_es21_rejects_table_without_hours() -> None:
    framework = _framework()
    framework["chapters"][7]["body"] = [
        {
            "block": "table",
            "caption": "What we need from the client",
            "columns": ["Category", "Specifically", "Status", "Owner"],
            "rows": [["Access", "named", "open", "IT"]],
        }
    ]
    with pytest.raises(ChapterValidationError) as exc_info:
        validate_all_chapters(framework)
    assert "hours" in exc_info.value.user_message
