"""Customer-report gates, evolution, guardrails, 14-chapter structure."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.eligibility import EligibilityError, check_eligibility, render_decision
from services.framework.evolution import generate_evolution
from services.framework.guardrails import lint_customer_texts, lint_numbers, strip_citations
from services.framework.pipeline import generate_customer_framework
from services.framework.rendering.customer_pdf import render_customer_pdf

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"
REGISTRY = json.loads(
    (Path(__file__).resolve().parents[3] / "packages" / "contracts" / "chapter_registry.json").read_text(
        encoding="utf-8"
    )
)


def _golden_models() -> tuple[list[dict], dict]:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    return [model], overrides


def test_eligibility_rejects_quality_below_50() -> None:
    with pytest.raises(EligibilityError):
        check_eligibility(conversation_quality=49, has_knowledge=True)


def test_readiness_below_60_does_not_render() -> None:
    decision = render_decision(59, [])
    assert decision["allowed"] is False
    assert decision["band"] == "not_ready"


def test_readiness_60_to_80_renders_with_assumptions_banner() -> None:
    decision = render_decision(72, [{"item_type": "assumption"}])
    assert decision["allowed"] is True
    assert decision["assumptions_banner"] is True
    assert decision["band"] == "ready_with_assumptions"


def test_stage3_without_source_is_dropped() -> None:
    stages = generate_evolution(
        today_description="Manual match",
        stage2_agent_does="Posts clean matches",
        stage2_human_does="Exceptions",
        stage2_benefit="full case",
        stage2_effort="3 weeks",
        stage3_candidates=[{"description": "Invented extra agent", "source_ref": ""}],
    )
    assert len(stages) == 4
    assert "No sourced stage-3" in stages[-1]["agent_does"]
    assert stages[2]["recommended"] is True


def test_citations_are_stripped_from_customer_view() -> None:
    assert "[C6:t14]" not in strip_citations("Posted on match [C6:t14] as confirmed.")
    assert "turn:26" not in strip_citations("Posted as confirmed turn:26 in the ERP.")


def test_turn_pointers_are_not_treated_as_customer_numbers() -> None:
    errors = lint_numbers(
        {"numbers": {"all_tokens": [], "blob": ""}},
        "C1 SPEAKER_6 turn:26 C1 SPEAKER_6 turn:38",
    )
    assert errors == []


def test_percent_named_in_knowledge_model_is_allowed() -> None:
    errors = lint_numbers(
        {"numbers": {"blob": "About 75% of invoices are clean", "percent_mentions": [75.0], "all_tokens": ["75"]}},
        "About 75% of invoices are clean",
    )
    assert errors == []


def test_guardrail_rejects_person_evaluative_language() -> None:
    errors = lint_customer_texts({"chapters": [{"body": "The AP clerk is lazy and incompetent."}]})
    assert errors


def test_golden_pipeline_has_fourteen_registry_chapters() -> None:
    models, overrides = _golden_models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    assert len(framework["chapters"]) == 14
    actual = [(ch["chapter_id"], ch["title"]) for ch in framework["chapters"]]
    expected = [(item["chapter_id"], item["title"]) for item in REGISTRY["chapters"]]
    assert actual == expected
    assert framework["quality_scores"]["opportunity_rating"] == 85
    assert framework["quality_scores"]["conversation_quality"] == 82
    assert framework["quality_scores"]["build_readiness"] == 94
    rationale = framework["quality_scores"]["rationale"]
    for key in ("opportunity_rating", "conversation_quality", "build_readiness"):
        assert rationale[key]
        assert "\n" not in rationale[key]
    assert framework["business_case"]["net_eur_mo"] == 2400
    assert framework["estimate"]["effort_weeks"]["min"] < framework["estimate"]["effort_weeks"]["likely"]
    assert framework["render"]["allowed"] is True
    ch11 = framework["chapters"][11]["body"]
    assert any(isinstance(block, dict) and block.get("block") == "score_bars" for block in ch11)


def test_chapter_6_openapi_wording_is_scrubbed() -> None:
    from services.framework.chapter_validators.ch06_how_built import scrub_technical_depth

    body = [
        {"block": "prose", "text": "No OpenAPI or JSON schema. No pseudocode or payload example."},
        {"block": "ai_split", "used_for": ["reading"], "not_used_for": ["deciding"]},
    ]
    cleaned = str(scrub_technical_depth(body)).lower()
    assert "openapi" not in cleaned
    assert "json schema" not in cleaned
    assert "pseudocode" not in cleaned
    assert "payload example" not in cleaned


def test_golden_customer_pdf_is_non_empty_and_footers_model_id() -> None:
    models, overrides = _golden_models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    pdf = render_customer_pdf(framework, lang="en")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000
    assert framework["id"] == "FW-OPP-142-v1"
    assert framework["render"]["band"] == "ready_to_build"
    assert b"60 and 80" not in pdf


def test_named_hours_use_automatable_core_not_target_remaining() -> None:
    from services.framework.assembly import assemble_from_knowledge

    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-142")
    assert skeleton["engine_inputs"]["automatable_hours_mo"] == 73
    assert skeleton["engine_inputs"]["hours_mo"] == 306
    assert skeleton["engine_inputs"]["loaded_hourly_cost_eur"] == 45
    assert skeleton["engine_inputs"]["automation_rate"] == 0.85
    assert len(skeleton["systems"]) == 2

    framework = generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
    )
    assert framework["business_case"]["inputs"]["automatable_hours_mo"] == 73
    assert framework["business_case"]["net_eur_mo"] == 2400
    classification = ""
    for block in framework["chapters"][8]["body"]:
        if block.get("block") != "kv_rows":
            continue
        for row in block.get("rows") or []:
            if "classification" in str(row.get("label", "")).lower():
                classification = str(row.get("value") or "").lower()
    assert "confidential" in classification
    assert "not named" not in classification


def test_auto_match_baseline_zero_does_not_zero_the_rate() -> None:
    from services.framework.assembly import assemble_from_knowledge

    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    model["stated_requirements"] = [
        {
            "statement": "KPI auto-match rate baseline 0 percent today.",
            "source_refs": [{"conversation_id": "C6", "speaker_role": "Sandra", "excerpt_pointer": "turn:5"}],
            "origin": "USER_INPUT",
            "confidence": "high",
        },
        {
            "statement": "KPI auto-match rate target at least 85 percent.",
            "source_refs": [{"conversation_id": "C6", "speaker_role": "Sandra", "excerpt_pointer": "turn:5"}],
            "origin": "USER_INPUT",
            "confidence": "high",
        },
    ]
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-142")
    assert skeleton["engine_inputs"]["automation_rate"] == 0.85
