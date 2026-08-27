"""Customer-report gates, evolution, guardrails, 14-chapter structure."""

from __future__ import annotations

import json
from io import BytesIO
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


def _km_fact(
    statement: str,
    *,
    origin: str = "SOURCE_FACT",
    confidence: str = "high",
    turn: int = 1,
) -> dict:
    return {
        "statement": statement,
        "source_refs": [{"conversation_id": "C1", "speaker_role": "Client", "excerpt_pointer": f"turn:{turn}"}],
        "origin": origin,
        "confidence": confidence,
    }


def _km_requirement(statement: str, *, turn: int = 2) -> dict:
    return _km_fact(statement, origin="USER_INPUT", confidence="high", turn=turn)


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


def test_knowledge_entry_count_in_generation_prose_is_allowed() -> None:
    errors = lint_numbers(
        {"source_entries": [{}] * 15, "numbers": {"all_tokens": [], "blob": ""}},
        "Finance and IT stakeholders, 15 knowledge entries. Generated from framework-synthesis:v1.",
    )
    assert errors == []


def test_expense_qualitative_benefit_is_domain_specific() -> None:
    from services.framework.assembly import _qualitative_benefits

    benefits = _qualitative_benefits(
        [
            {
                "statement": (
                    "Month-end close slips by two days when the backlog hits 80 open expense reports."
                )
            },
            {"statement": "Today the team is reactive — they firefight exceptions instead of improving policy."},
        ]
    )
    assert any("expense-report backlog" in item for item in benefits)
    assert all("Accounts Payable" not in item for item in benefits)


def test_customer_view_strips_speaker_labels() -> None:
    from services.framework.guardrails import strip_citations

    assert "SPEAKER_2" not in strip_citations("SPEAKER_2 guessed maybe 75 percent.")
    assert "a business stakeholder" in strip_citations("SPEAKER_2 guessed maybe 75 percent.")
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
    assert framework["quality_scores"]["opportunity_rating"] == 68
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


def test_cover_meta_table_labels_use_white_text_on_navy_background() -> None:
    import pypdf

    from services.framework.rendering.customer_pdf import _meta_table, render_customer_pdf

    table = _meta_table([["Opportunity", "OPP-142"], ["Department", "Finance"]])
    assert "Opportunity" in str(table._cellvalues[0][0])

    models, overrides = _golden_models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    pdf = render_customer_pdf(framework, lang="en")
    text = pypdf.PdfReader(BytesIO(pdf)).pages[0].extract_text() or ""
    for label in ("Opportunity", "Department", "Status", "Priority"):
        assert label in text


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


def test_customer_declared_budget_run_cost_and_effort_override_engine_defaults() -> None:
    from services.framework.assembly import assemble_from_knowledge
    from services.framework.pipeline import run_engines

    model = {
        "conversation_id": "C1",
        "facts": [
            _km_fact("The repeatable core is 120 hours per month."),
            _km_fact("Reduce repeatable effort from 120 hours to no more than 35 hours per month."),
            _km_fact("The loaded labor rate is EUR 42 per hour."),
            _km_fact("The estimated monthly run cost is EUR 900."),
            _km_fact("The initial build budget is EUR 28,000."),
            _km_fact("The estimated build is six weeks with medium confidence."),
            _km_fact("The automation-rate KPI target is at least 70 percent."),
            _km_fact("The process handles 1,200 invoices per month."),
        ],
        "stated_requirements": [],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-DECLARED")
    engines = run_engines(skeleton, overrides={})

    assert skeleton["engine_inputs"]["declared_effort_weeks"] == 6
    assert skeleton["engine_inputs"]["build_cost_eur"] == 28_000
    assert skeleton["engine_inputs"]["run_cost_eur_mo"] == 900
    assert skeleton["engine_inputs"]["target_remaining_hours_mo"] == 35
    assert engines["estimate"]["effort_weeks"]["likely"] == 6
    assert engines["estimate"]["build_cost_eur"] == 28_000
    assert engines["business_case"]["hours_saved_mo"] == 85
    assert engines["business_case"]["gross_eur_mo"] == 3_570
    assert engines["business_case"]["net_eur_mo"] == 2_670
    assert engines["business_case"]["payback_months"] == 10.5
    assert engines["business_case"]["roi_36m_pct"] == 243


def test_reduction_statement_supplies_current_core_when_it_is_not_repeated() -> None:
    """ES-23: “reduce 120 to 35 hours each month” carries both business-case inputs."""
    from services.framework.assembly import assemble_from_knowledge
    from services.framework.pipeline import run_engines

    model = {
        "conversation_id": "C1",
        "facts": [
            _km_fact("The loaded labor rate is EUR 42 per hour."),
            _km_fact("The estimated monthly run cost is EUR 900."),
            _km_fact("The initial build budget is EUR 28,000."),
        ],
        "stated_requirements": [
            _km_requirement("Reduce repeatable manual effort from 120 hours to no more than 35 hours each month."),
            _km_requirement("The automation-rate KPI target is at least 70 percent."),
        ],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }

    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-REDUCTION")
    business = run_engines(skeleton, overrides={})["business_case"]

    assert skeleton["engine_inputs"]["automatable_hours_mo"] == 120
    assert skeleton["engine_inputs"]["target_remaining_hours_mo"] == 35
    assert business["hours_saved_mo"] == 85
    assert business["net_eur_mo"] == 2_670


def test_purchase_requisition_transcript_drives_volume_and_hour_target() -> None:
    """ES-23: requisitions volume and “to under 20 hours” feed the business case."""
    from services.framework.assembly import assemble_from_knowledge, harvest_numbers
    from services.framework.pipeline import run_engines

    transcript = (
        Path(__file__).resolve().parents[3] / "sample_transcripts" / "demo_purchase_requisition.txt"
    ).read_text(encoding="utf-8")
    facts = [
        _km_fact(line.split(": ", 1)[1], turn=index)
        for index, line in enumerate(
            (line for line in transcript.splitlines() if ": " in line and not line.startswith("Agent")),
            start=1,
        )
    ]
    model = {
        "conversation_id": "C1",
        "facts": facts,
        "stated_requirements": [],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }

    numbers = harvest_numbers(facts)
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-REQ")
    business = run_engines(skeleton, overrides={})["business_case"]

    assert numbers["monthly_volume"] == 850
    assert skeleton["engine_inputs"]["monthly_volume"] == 850
    assert skeleton["engine_inputs"]["automatable_hours_mo"] == 95
    assert skeleton["engine_inputs"]["target_remaining_hours_mo"] == 20
    assert skeleton["engine_inputs"]["loaded_hourly_cost_eur"] == 48
    assert skeleton["engine_inputs"]["automation_rate"] is None

    assert business["hours_saved_mo"] == 75
    assert business["inputs"]["automation_rate"] == pytest.approx(75 / 95, rel=1e-4)
    assert business["gross_eur_mo"] == 3_600
    assert business["run_cost_eur_mo"] == 150
    assert business["net_eur_mo"] == 3_450


def test_department_prefers_procurement_over_ap_in_sap() -> None:
    from services.framework.assembly import assemble_from_knowledge

    model = {
        "conversation_id": "C1",
        "facts": [
            _km_fact("Systems are SAP S/4HANA for requisitions, budgets, and suppliers."),
            _km_fact("That is roughly 95 hours per month for the whole procurement team."),
        ],
        "stated_requirements": [],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-DEPT")
    assert skeleton["department"] == "Procurement"


def test_derived_automation_rate_survives_customer_guardrails() -> None:
    from services.framework.pipeline import generate_customer_framework

    model = {
        "conversation_id": "C1",
        "facts": [
            _km_fact("Process about 850 purchase requisitions per month across three business units."),
            _km_fact("Current process requires roughly 95 hours per month in the repeatable core."),
            _km_requirement("Cut manual checking time from 95 hours per month to under 20 hours.", turn=5),
            _km_fact("Loaded cost is EUR 48 per hour.", turn=8),
        ],
        "stated_requirements": [],
        "constraints": [],
        "named_systems": [],
        "named_rules": [],
        "named_exceptions": [],
        "people_and_roles": [],
        "timeline_mentions": [],
        "risks": [],
        "unknowns": [],
    }
    framework = generate_customer_framework(
        [model],
        opportunity_id="OPP-RATE-DISPLAY",
        title_hint="Purchase Requisition Approval",
        use_llm=False,
    )
    ch9 = next(ch for ch in framework["chapters"] if str(ch.get("chapter_id")) == "9")
    table = next(block for block in ch9["body"] if block.get("block") == "table")
    rate_row = next(row for row in table["rows"] if row[0] == "Automation rate")
    assert "open item" not in rate_row[2].lower()
    assert any(token in rate_row[2] for token in ("79", "78.9"))
    sensitivity = next(block for block in ch9["body"] if block.get("block") == "sensitivity")
    assert "Auto-match" not in str(sensitivity)
    assert "Automation rate" in str(sensitivity)
