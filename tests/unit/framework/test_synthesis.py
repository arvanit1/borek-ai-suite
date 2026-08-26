"""ES-9 — one Claude call produces all 14 customer-report chapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.pipeline import generate_customer_framework
from services.framework.synthesis import (
    PROMPT_VERSION,
    FrameworkSynthesisError,
    synthesize_customer_draft,
)

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"
REGISTRY = json.loads(
    (Path(__file__).resolve().parents[3] / "packages" / "contracts" / "chapter_registry.json").read_text(
        encoding="utf-8"
    )
)


def _golden() -> tuple[list[dict], dict]:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    return [model], overrides


def _base_framework() -> dict:
    models, overrides = _golden()
    return generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )


def _draft_from_framework(framework: dict) -> dict:
    fallback_ref = {
        "conversation_id": "C6",
        "speaker_role": "Sandra",
        "excerpt_pointer": "turn:0",
    }
    chapters = []
    for chapter in framework["chapters"]:
        refs = list(chapter.get("source_refs") or []) or [fallback_ref]
        chapters.append(
            {
                "chapter_id": chapter["chapter_id"],
                "title": chapter["title"],
                "body": chapter["body"],
                "source_refs": refs,
            }
        )
    return {
        "title": framework["title"],
        "department": framework["department"],
        "cover": {
            "tagline": framework["cover"].get("tagline") or "Customer framework report.",
            "sources_line": framework["cover"].get("sources_line") or "Sources C6",
            "how_produced": framework["cover"].get("how_produced") or "Generated from conversations.",
        },
        "kpis": [
            {
                "name": item.get("name") or "KPI",
                "baseline": str(item.get("baseline") or ""),
                "target": str(item.get("target") or ""),
                "measured_via": str(item.get("measured_via") or ""),
            }
            for item in framework.get("kpis") or []
        ],
        "systems": [
            {
                "name": item.get("name") or "System",
                "role": item.get("role") or "named",
                "direction": item.get("direction") or "internal",
                "access_path": item.get("access_path") or "as named",
                "data_classification": item.get("data_classification") or "as reported",
                "status": item.get("status") or "available",
            }
            for item in framework.get("systems") or []
        ],
        "rules": [
            {"name": item.get("name") or "Rule", "logic": item.get("logic") or item.get("name") or "named"}
            for item in framework.get("rules") or []
        ],
        "exceptions": [
            {
                "name": item.get("name") or "Exception",
                "frequency": item.get("frequency") or "named",
                "handling": item.get("handling") or "queued",
            }
            for item in framework.get("exceptions") or []
        ],
        "access_needs": [
            {
                "category": item.get("category") or "Access",
                "detail": item.get("detail") or "named",
                "status": item.get("status") or "named in conversation",
                "owner": item.get("owner") or "IT",
            }
            for item in framework.get("access_needs") or []
        ],
        "open_items": [
            {
                "description": item.get("description") or "Open item",
                "item_type": item.get("item_type")
                if item.get("item_type") in {"dependency", "assumption"}
                else "assumption",
                "owner": item.get("owner") or "Business",
                "consequence_if_different": item.get("consequence_if_different") or "Confirm before build.",
            }
            for item in framework.get("open_items") or []
        ],
        "chapters": chapters,
    }


def test_one_claude_call_returns_all_fourteen_registry_chapters() -> None:
    base = _base_framework()
    draft = _draft_from_framework(base)
    calls: list[str] = []

    def complete(system: str, user: str, schema: dict) -> dict:
        calls.append(system)
        assert PROMPT_VERSION in system
        assert "About this document" in system
        assert "ENGINE OUTPUTS" in user
        assert schema["title"] == "CustomerReportDraft"
        return draft

    result = synthesize_customer_draft(
        skeleton={"opportunity_id": "OPP-142", "title": "Invoice 3-Way Match"},
        engine_outputs={"quality_scores": base["quality_scores"]},
        complete=complete,
    )
    assert len(calls) == 1
    actual = [(ch["chapter_id"], ch["title"]) for ch in result["chapters"]]
    expected = [(item["chapter_id"], item["title"]) for item in REGISTRY["chapters"]]
    assert actual == expected
    assert len(result["chapters"]) == 14


def test_missing_chapter_fails_validation() -> None:
    draft = _draft_from_framework(_base_framework())
    draft["chapters"] = draft["chapters"][:13]

    def complete(system: str, user: str, schema: dict) -> dict:
        return draft

    with pytest.raises(FrameworkSynthesisError) as exc_info:
        synthesize_customer_draft(skeleton={}, engine_outputs={}, complete=complete)
    assert "14" in exc_info.value.user_message


def test_claude_extra_cover_fields_are_coerced() -> None:
    draft = _draft_from_framework(_base_framework())
    draft["cover"]["status_label"] = "READY TO BUILD"
    draft["chapters"][0]["chapter_id"] = 0
    draft["chapters"][0]["source_refs"][0]["excerpt_pointer"] = 0

    def complete(system: str, user: str, schema: dict) -> dict:
        return draft

    result = synthesize_customer_draft(skeleton={}, engine_outputs={}, complete=complete)
    assert "status_label" not in result["cover"]
    assert result["chapters"][0]["chapter_id"] == "0"
    assert result["chapters"][0]["source_refs"][0]["excerpt_pointer"] == "turn:0"


def test_pipeline_uses_single_llm_call() -> None:
    models, overrides = _golden()
    base = _base_framework()
    draft = _draft_from_framework(base)
    calls: list[int] = []

    def complete(system: str, user: str, schema: dict) -> dict:
        calls.append(1)
        assert "KNOWLEDGE ENTRIES" in user
        return draft

    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=True,
        complete=complete,
        engine_overrides=overrides,
    )
    assert len(calls) == 1
    assert len(framework["chapters"]) == 14
    assert framework["generation_meta"]["llm_used"] is True
    assert framework["generation_meta"]["prompt_version"] == PROMPT_VERSION
    ch6 = str(framework["chapters"][6]["body"]).lower()
    assert "pseudocode" not in ch6


def test_llm_overlay_keeps_required_chapter_blocks() -> None:
    models, overrides = _golden()
    base = _base_framework()
    draft = _draft_from_framework(base)
    draft["chapters"][0]["body"] = [{"block": "prose", "text": "A customer report from the conversations."}]
    draft["chapters"][1]["body"] = [
        {"block": "prose", "text": "Invoice matching is a repeatable task with named volume and cost."},
        {"block": "kv_rows", "caption": "At a glance", "rows": [{"label": "Volume", "value": "named"}]},
        {
            "block": "callout",
            "kind": "recommendation",
            "text": "Release at evolution stage 2 with human control. Blocking items are in chapter 11.",
        },
    ]
    draft["chapters"][5]["body"] = [
        {"block": "prose", "text": "Rules come from the conversations. The team decides; the agent never acts on its own."},
        {"block": "kv_rows", "caption": "How it works", "rows": [{"label": "Start", "value": "named"}]},
        {"block": "table", "caption": "Rules", "columns": ["Rule"], "rows": [["named"]]},
        {"block": "table", "caption": "Exceptions", "columns": ["Exception"], "rows": [["named"]]},
    ]
    draft["chapters"][7]["body"] = [
        {
            "block": "table",
            "caption": "What we need from the client",
            "columns": ["Category", "Specifically", "Status", "Owner"],
            "rows": [["Access", "named", "open", "IT"]],
        }
    ]
    draft["chapters"][8]["body"] = [{"block": "prose", "text": "Security is taken seriously."}]

    def complete(system: str, user: str, schema: dict) -> dict:
        return draft

    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=True,
        complete=complete,
        engine_overrides=overrides,
    )
    ch0_body = framework["chapters"][0]["body"]
    ch1_body = framework["chapters"][1]["body"]
    ch5_body = framework["chapters"][5]["body"]
    ch7_body = framework["chapters"][7]["body"]
    ch8_body = framework["chapters"][8]["body"]
    ch0 = str(ch0_body).lower()
    ch1 = str(ch1_body).lower()
    ch5 = str(ch5_body).lower()
    ch7 = str(ch7_body).lower()
    ch8 = str(ch8_body).lower()
    assert "what is it" in ch0
    assert "generated" in ch0
    assert "human-confirmed" in ch0
    assert "human in the loop" in ch1
    assert "trigger" in ch5
    assert "input" in ch5
    assert "result" in ch5
    assert "hour" in ch7
    assert "classification" in ch8
    assert "residency" in ch8
    assert len([block for block in ch0_body if block.get("block") == "bullets"]) == 1
    assert len([block for block in ch1_body if block.get("block") == "kv_rows"]) == 1
    assert len([block for block in ch5_body if block.get("block") == "kv_rows"]) == 1
    assert len([block for block in ch5_body if block.get("block") == "table"]) == 2
    assert len([block for block in ch7_body if block.get("block") == "table"]) == 1
    hours_cols = " ".join(str(col) for col in ch7_body[0]["columns"]).lower()
    assert "hour" in hours_cols


def test_missing_payback_is_listed_not_guessed() -> None:
    models, _ = _golden()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides={"hours_mo": 0, "automatable_hours_mo": 0, "monthly_volume": 0},
    )
    assert framework["business_case"]["payback_months"] is None
    assert any("payback" in str(item.get("description", "")).lower() for item in framework["open_items"])
    chapter9 = str(framework["chapters"][9]["body"]).lower()
    assert "payback" in chapter9
    assert "~none" not in chapter9


def test_llm_overlay_replaces_wrong_eight_questions_once() -> None:
    models, overrides = _golden()
    base = _base_framework()
    draft = _draft_from_framework(base)
    draft["chapters"][0]["body"] = [
        {
            "block": "prose",
            "text": (
                "This generated report is human-confirmed. Every number is traceable. "
                "Estimates are ranges, never false precision."
            ),
        },
        {
            "block": "bullets",
            "items": [
                "What is the business goal and how do we measure success?",
                "How does the process work today, and what will change?",
                "What does the agent do, and what stays with people?",
                "How is it built, and what do we need from IT and the business?",
                "Is it secure, and how do we stay in control?",
                "What is the business case, and when do we break even?",
                "How complex is it, and how long will it take?",
                "How trustworthy is the plan, and what is still open?",
            ],
        },
    ]

    def complete(system: str, user: str, schema: dict) -> dict:
        return draft

    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=True,
        complete=complete,
        engine_overrides=overrides,
    )
    bullets = [block for block in framework["chapters"][0]["body"] if block.get("block") == "bullets"]
    assert len(bullets) == 1
    assert len(bullets[0]["items"]) == 8
    joined = " ".join(bullets[0]["items"]).lower()
    assert "what is it" in joined
    assert "why do it" in joined
    assert joined.count("what is it") == 1


def test_llm_overlay_restores_every_required_live_validation_field() -> None:
    models, overrides = _golden()
    draft = _draft_from_framework(_base_framework())
    draft["kpis"] = [
        {"name": "Manual handling time", "baseline": "named", "target": "named", "measured_via": "named"}
    ]
    draft["chapters"][2]["body"] = [
        {"block": "process_flow", "caption": "Today", "nodes": [], "edges": []},
        {"block": "kv_rows", "caption": "Cost", "rows": [{"label": "Volume", "value": "named"}]},
    ]
    draft["chapters"][3]["body"] = [{"block": "table", "caption": "KPIs", "columns": ["KPI"], "rows": []}]
    draft["chapters"][4]["body"] = [
        {"block": "process_flow", "caption": "Stage 2", "nodes": [], "edges": []},
        {"block": "table", "caption": "Comparison", "columns": ["Before", "After"], "rows": []},
    ]
    draft["chapters"][6]["body"] = [
        {"block": "table", "caption": "Building blocks", "columns": ["Block"], "rows": [["Queue"]]},
        {"block": "ai_split", "used_for": ["Extract"], "not_used_for": ["Approve"]},
    ]
    draft["chapters"][8]["body"] = [
        {"block": "kv_rows", "caption": "Guardrails", "rows": [{"label": "Audit", "value": "named"}]}
    ]

    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=True,
        complete=lambda _system, _user, _schema: draft,
        engine_overrides=overrides,
    )
    assert any(block.get("block") == "process_flow" and len(block.get("nodes") or []) >= 2 for block in framework["chapters"][2]["body"])
    assert all(token in str(framework["chapters"][2]["body"]).lower() for token in ("clean", "exception", "staff"))
    names = " ".join(item["name"].lower() for item in framework["kpis"])
    assert "auto-match" in names
    assert "success" in names
    assert "today" in str(framework["chapters"][4]["body"]).lower()
    assert "agent" in str(framework["chapters"][4]["body"]).lower()
    assert "protect" in str(framework["chapters"][6]["body"]).lower()
    assert "retention" in str(framework["chapters"][8]["body"]).lower()
