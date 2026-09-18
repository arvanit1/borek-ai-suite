"""Live LLM overlay must restore ES chapter invariants before validate_all_chapters."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from services.framework.chapter_builder import overlay_llm_chapters, reconcile_chapter_invariants
from services.framework.chapter_validators import validate_all_chapters
from services.framework.chapter_validators.ch00_about import has_eight_decision_questions
from services.framework.chapter_validators.ch03_aim_success import has_conservative_marker, validate as validate_ch03
from services.framework.chapter_validators.ch05_how_it_works import has_never_autonomous_statement
from services.framework.chapter_validators.ch06_how_built import has_building_protection, validate as validate_ch06
from services.framework.chapter_validators.base import chapter_blob
from services.framework.cross_chapter_rules import enforce_cross_chapter_rules
from services.framework.guardrails import convert_unsourced_claims
from services.framework.pre_confirm_check import prepare_framework_for_confirm
from services.framework.company_facts import ground_company_facts
from services.framework.pipeline import generate_customer_framework
from services.framework.source_traceability import convert_unsupported_block_claims
from services.framework.synthesis import apply_draft_to_chapters

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


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
                "body": copy.deepcopy(chapter["body"]),
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
        "kpis": copy.deepcopy(framework.get("kpis") or []),
        "systems": copy.deepcopy(framework.get("systems") or []),
        "rules": copy.deepcopy(framework.get("rules") or []),
        "exceptions": copy.deepcopy(framework.get("exceptions") or []),
        "access_needs": copy.deepcopy(framework.get("access_needs") or []),
        "open_items": copy.deepcopy(framework.get("open_items") or []),
        "chapters": chapters,
    }


def _chapter(chapters: list[dict], chapter_id: str) -> dict:
    return next(chapter for chapter in chapters if str(chapter.get("chapter_id")) == chapter_id)


def _break_live_style_chapters(draft: dict) -> None:
    _chapter(draft["chapters"], "0")["body"] = [
        {
            "block": "prose",
            "text": "This report is generated and human-confirmed. Numbers are traceable. Estimates are ranges, never false precision.",
        },
        {"block": "bullets", "items": ["Summary of the meeting", "Next steps"]},
    ]
    ch3 = _chapter(draft["chapters"], "3")
    for block in ch3["body"]:
        if isinstance(block, dict) and block.get("block") == "prose":
            block["text"] = "These KPIs come from the conversations. Empty cells are open items, not guesses."
    ch6 = _chapter(draft["chapters"], "6")
    replaced = False
    for index, block in enumerate(ch6["body"]):
        if not isinstance(block, dict) or block.get("block") != "table":
            continue
        caption = str(block.get("caption") or "").lower()
        columns = " ".join(str(col) for col in (block.get("columns") or [])).lower()
        if "building block" in caption or "building block" in columns:
            ch6["body"][index] = {
                "block": "table",
                "caption": "Building blocks",
                "columns": ["Building block", "How it works", "Protection"],
                "rows": [["X", "Y", "Human review"]],
            }
            replaced = True
            break
    assert replaced


def test_overlay_repairs_chapter_6_human_review_protection() -> None:
    base = _base_framework()
    draft = _draft_from_framework(base)
    _break_live_style_chapters(draft)
    merged = overlay_llm_chapters(base["chapters"], draft["chapters"])
    chapter = _chapter(merged, "6")
    assert has_building_protection(chapter)
    assert validate_ch06(base, chapter) == []
    table = next(
        block
        for block in chapter["body"]
        if block.get("block") == "table" and "building block" in str(block).lower()
    )
    assert "protect" in str(table).lower()
    assert "Human review" not in str(table.get("rows"))


def test_overlay_repairs_empty_and_arbitrary_protection() -> None:
    base = _base_framework()
    draft = _draft_from_framework(base)
    ch6 = _chapter(draft["chapters"], "6")
    for wording in ("", "Control gate", "Owner sign-off"):
        mutated = copy.deepcopy(ch6)
        for index, block in enumerate(mutated["body"]):
            if isinstance(block, dict) and "building block" in str(block).lower():
                mutated["body"][index] = {
                    "block": "table",
                    "caption": "Building blocks",
                    "columns": ["Building block", "Role", "Protection"],
                    "rows": [["Extractor", "Reads invoices", wording]],
                }
        merged = overlay_llm_chapters(base["chapters"], [mutated])
        assert has_building_protection(_chapter(merged, "6"))


def test_overlay_keeps_valid_protection_wording() -> None:
    base = _base_framework()
    draft = _draft_from_framework(base)
    ch6 = _chapter(draft["chapters"], "6")
    kept = "Protected by least-privilege access and human release"
    for index, block in enumerate(ch6["body"]):
        if isinstance(block, dict) and "building block" in str(block).lower():
            ch6["body"][index] = {
                "block": "table",
                "caption": "Building blocks",
                "columns": ["Building block", "Role in the automation", "How it is protected"],
                "rows": [["Extractor", "Reads invoices", kept]],
            }
    merged = overlay_llm_chapters(base["chapters"], draft["chapters"])
    table = next(
        block
        for block in _chapter(merged, "6")["body"]
        if block.get("block") == "table" and "building block" in str(block).lower()
    )
    assert table["rows"][0][2] == kept


def test_overlay_restores_chapter_3_conservative_marker() -> None:
    base = _base_framework()
    draft = _draft_from_framework(base)
    _break_live_style_chapters(draft)
    merged = overlay_llm_chapters(base["chapters"], draft["chapters"])
    chapter = _chapter(merged, "3")
    assert has_conservative_marker(chapter)
    assert validate_ch03(base, chapter) == []


def test_overlay_restores_chapter_0_decision_questions() -> None:
    base = _base_framework()
    draft = _draft_from_framework(base)
    _break_live_style_chapters(draft)
    merged = overlay_llm_chapters(base["chapters"], draft["chapters"])
    chapter = _chapter(merged, "0")
    assert has_eight_decision_questions(chapter)


def test_reconcile_restores_markers_lost_after_prepare_for_confirm() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    prepare_framework_for_confirm(framework)
    broken = {"chapters": copy.deepcopy(framework["chapters"])}
    _break_live_style_chapters(broken)
    framework["chapters"] = broken["chapters"]
    assert not has_eight_decision_questions(_chapter(framework["chapters"], "0"))
    assert not has_conservative_marker(_chapter(framework["chapters"], "3"))
    assert not has_building_protection(_chapter(framework["chapters"], "6"))
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    validate_all_chapters(framework)


def test_pipeline_live_style_mutations_do_not_fail_chapter_validation() -> None:
    models, overrides = _golden()
    base = _base_framework()
    draft = _draft_from_framework(base)
    _break_live_style_chapters(draft)
    calls: list[int] = []

    def complete(system: str, user: str, schema: dict) -> dict:
        calls.append(1)
        return draft

    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=True,
        complete=complete,
        engine_overrides=overrides,
    )
    assert calls == [1]
    validate_all_chapters(framework)
    assert has_eight_decision_questions(_chapter(framework["chapters"], "0"))
    assert has_conservative_marker(_chapter(framework["chapters"], "3"))
    assert has_building_protection(_chapter(framework["chapters"], "6"))


def test_apply_draft_to_chapters_uses_validator_safe_overlay() -> None:
    base = _base_framework()
    draft = _draft_from_framework(base)
    _break_live_style_chapters(draft)
    merged = apply_draft_to_chapters(base["chapters"], draft)
    validate_all_chapters({**base, "chapters": merged})


def test_reconcile_is_no_op_for_valid_framework() -> None:
    framework = _base_framework()
    before = copy.deepcopy(framework["chapters"])
    after = reconcile_chapter_invariants(framework["chapters"], before)
    assert after == before


def test_reconcile_is_idempotent() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    broken = _draft_from_framework(framework)
    _break_live_style_chapters(broken)
    once = reconcile_chapter_invariants(broken["chapters"], base_chapters)
    twice = reconcile_chapter_invariants(once, base_chapters)
    assert once == twice


def test_reconcile_preserves_chapter_1_when_valid() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch1_before = copy.deepcopy(_chapter(framework["chapters"], "1"))
    broken = _draft_from_framework(framework)
    _break_live_style_chapters(broken)
    merged = reconcile_chapter_invariants(broken["chapters"], base_chapters)
    assert _chapter(merged, "1") == ch1_before


def test_reconcile_preserves_unrelated_chapters() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch2_before = copy.deepcopy(_chapter(framework["chapters"], "2"))
    ch5_before = copy.deepcopy(_chapter(framework["chapters"], "5"))
    broken = _draft_from_framework(framework)
    _break_live_style_chapters(broken)
    merged = reconcile_chapter_invariants(broken["chapters"], base_chapters)
    assert _chapter(merged, "2") == ch2_before
    assert _chapter(merged, "5") == ch5_before


def test_reconcile_preserves_company_facts() -> None:
    models, overrides = _golden()
    grounding = ground_company_facts("Invoice 3-Way Match")
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
        company_facts=grounding,
    )
    base_chapters = copy.deepcopy(
        generate_customer_framework(
            models,
            opportunity_id="OPP-142",
            title_hint="Invoice 3-Way Match",
            use_llm=False,
            engine_overrides=overrides,
        )["chapters"]
    )
    before_text = json.dumps(framework["chapters"])
    assert "1250.00" in before_text
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    after_text = json.dumps(framework["chapters"])
    assert "1250.00" in after_text
    validate_all_chapters(framework)


def test_minimal_ch6_protection_repair_keeps_other_blocks() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch6_before = copy.deepcopy(_chapter(framework["chapters"], "6"))
    ai_split = next(block for block in ch6_before["body"] if block.get("block") == "ai_split")
    draft = _draft_from_framework(framework)
    _break_live_style_chapters(draft)
    merged = reconcile_chapter_invariants(draft["chapters"], base_chapters)
    ch6 = _chapter(merged, "6")
    assert has_building_protection(ch6)
    assert next(block for block in ch6["body"] if block.get("block") == "ai_split") == ai_split


def _post_prepare_chain(framework: dict, base: dict, base_chapters: list[dict]) -> None:
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    convert_unsupported_block_claims(framework, base.get("source_entries") or [])
    enforce_cross_chapter_rules(framework, base.get("source_entries") or [])
    convert_unsourced_claims(framework)
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)


def _minimal_framework() -> dict:
    model = json.loads((FIXTURES / "knowledge_model.minimal.json").read_text(encoding="utf-8"))
    return generate_customer_framework(
        [model],
        opportunity_id=str(model["opportunity_id"]),
        title_hint="Invoice Automation",
        use_llm=False,
    )


def test_chapter_5_never_autonomous_survives_full_post_processing_chain() -> None:
    framework = _minimal_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch5 = _chapter(framework["chapters"], "5")
    ch5["body"] = [block for block in ch5["body"] if block.get("block") != "callout"]
    prepare_framework_for_confirm(framework)
    _post_prepare_chain(framework, framework, base_chapters)
    assert has_never_autonomous_statement(_chapter(framework["chapters"], "5"))
    validate_all_chapters(framework)


def test_chapter_5_never_autonomous_restored_before_final_validation() -> None:
    framework = _minimal_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch5 = _chapter(framework["chapters"], "5")
    ch5["body"] = [block for block in ch5["body"] if block.get("block") != "callout"]
    prepare_framework_for_confirm(framework)
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    convert_unsupported_block_claims(framework, framework.get("source_entries") or [])
    assert not has_never_autonomous_statement(_chapter(framework["chapters"], "5"))
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    assert has_never_autonomous_statement(_chapter(framework["chapters"], "5"))


def test_chapter_5_valid_wording_is_not_overwritten() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch5_before = copy.deepcopy(_chapter(framework["chapters"], "5"))
    merged = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    assert _chapter(merged, "5") == ch5_before


def test_chapter_10_ch12_alignment_survives_full_post_processing_chain() -> None:
    framework = _minimal_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch10 = _chapter(framework["chapters"], "10")
    ch10["body"] = [
        block
        for block in ch10["body"]
        if block.get("block") not in {"prose", "timeline"}
    ] + [
        {
            "block": "prose",
            "text": "Phased delivery over three weeks with go-live approval at the end.",
        },
        {
            "block": "timeline",
            "weeks": [{"id": "W1", "items": ["Sprint work"]}],
        },
    ]
    prepare_framework_for_confirm(framework)
    _post_prepare_chain(framework, framework, base_chapters)
    blob = chapter_blob(_chapter(framework["chapters"], "10")).lower()
    assert "chapter 12" in blob or "ch.12" in blob
    validate_all_chapters(framework)


def test_chapter_10_ch12_alignment_restored_before_final_validation() -> None:
    framework = _minimal_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch10 = _chapter(framework["chapters"], "10")
    ch10["body"] = [
        {
            "block": "prose",
            "text": "Phased delivery over three weeks with go-live approval at the end.",
        },
        {
            "block": "timeline",
            "weeks": [{"id": "W1", "items": ["Sprint work"]}],
        },
    ]
    merged = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    blob = chapter_blob(_chapter(merged, "10")).lower()
    assert "chapter 12" in blob or "ch.12" in blob


def test_chapter_10_valid_alignment_prose_is_not_duplicated() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch10_before = copy.deepcopy(_chapter(framework["chapters"], "10"))
    merged = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    assert _chapter(merged, "10") == ch10_before


def test_chapter_5_and_10_unrelated_content_unchanged_after_reconcile() -> None:
    framework = _base_framework()
    base_chapters = copy.deepcopy(framework["chapters"])
    ch5 = _chapter(framework["chapters"], "5")
    for block in ch5["body"]:
        if block.get("block") == "table" and "rule" in str(block).lower():
            block["rows"] = [["Custom rule", "From transcript"]]
    ch10 = _chapter(framework["chapters"], "10")
    drivers = next(
        row
        for block in ch10["body"]
        if block.get("block") == "kv_rows"
        for row in (block.get("rows") or [])
        if isinstance(row, dict) and "driver" in str(row.get("label", "")).lower()
    )
    drivers["value"] = "custom-driver-token"
    merged = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    merged_ch5 = _chapter(merged, "5")
    merged_ch10 = _chapter(merged, "10")
    assert any("Custom rule" in str(block) for block in merged_ch5["body"])
    assert any("custom-driver-token" in str(block) for block in merged_ch10["body"])


def test_pipeline_reconciliation_survives_es28_second_pass() -> None:
    models, overrides = _golden()
    base = _base_framework()
    draft = _draft_from_framework(base)
    _break_live_style_chapters(draft)
    chapters = overlay_llm_chapters(base["chapters"], draft["chapters"])
    base_chapters = copy.deepcopy(base["chapters"])
    framework = copy.deepcopy(base)
    framework["chapters"] = chapters
    prepare_framework_for_confirm(framework)
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    convert_unsupported_block_claims(framework, framework.get("source_entries") or [])
    framework["chapters"] = reconcile_chapter_invariants(framework["chapters"], base_chapters)
    validate_all_chapters(framework)
    ch1 = _chapter(framework["chapters"], "1")
    assert any(block.get("block") == "prose" for block in ch1["body"])
    assert _chapter(framework["chapters"], "2") == _chapter(base["chapters"], "2")
