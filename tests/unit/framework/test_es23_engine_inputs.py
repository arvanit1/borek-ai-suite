"""ES-23 typed-metric harvest, ES-7 origin gating, ES-28 number guardrails."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.assembly import allowed_customer_numbers, assemble_from_knowledge
from services.framework.guardrails import lint_numbers, _flatten_customer_text
from services.framework.pipeline import generate_customer_framework, run_engines

ROOT = Path(__file__).resolve().parents[3]
KM_PATH = ROOT / "packages/contracts/fixtures/knowledge_model.purchase_requisition.json"


def _km_fact(
    statement: str,
    *,
    origin: str = "SOURCE_FACT",
    confidence: str = "high",
    turn: int = 1,
    metric: dict | None = None,
) -> dict:
    entry = {
        "statement": statement,
        "source_refs": [{"conversation_id": "C1", "speaker_role": "Client", "excerpt_pointer": f"turn:{turn}"}],
        "origin": origin,
        "confidence": confidence,
    }
    if metric is not None:
        entry["metric"] = metric
    return entry


def _purchase_requisition_km_model() -> dict:
    return json.loads(KM_PATH.read_text(encoding="utf-8"))


def test_es23_stored_km_with_origin_fields_harvests_client_numbers() -> None:
    skeleton = assemble_from_knowledge([_purchase_requisition_km_model()], opportunity_id="OPP-KM-TRACE")
    inputs = skeleton["engine_inputs"]
    assert inputs["monthly_volume"] == 850
    assert inputs["automatable_hours_mo"] == 95
    assert inputs["target_remaining_hours_mo"] == 20
    assert inputs["loaded_hourly_cost_eur"] == 48


def test_es23_typed_metric_preferred_over_statement_regex() -> None:
    model = {
        "conversation_id": "C1",
        "facts": [
            _km_fact(
                "Monthly volume is 850 requisitions across three business units.",
                metric={"kind": "monthly_volume", "value": 850},
            ),
            _km_fact(
                "Repeatable core work is 95 hours in the repeatable core each month.",
                metric={"kind": "automatable_hours_mo", "value": 95},
            ),
            _km_fact(
                "Success means cutting manual checking from 95 hours to under 20 hours monthly.",
                origin="USER_INPUT",
                metric={"kind": "target_remaining_hours_mo", "value": 20},
            ),
            _km_fact(
                "Loaded cost is EUR 48 per hour.",
                metric={"kind": "loaded_hourly_cost_eur", "value": 48},
            ),
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
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-METRIC")
    business = run_engines(skeleton, overrides={})["business_case"]
    assert skeleton["engine_inputs"]["monthly_volume"] == 850
    assert business["hours_saved_mo"] == 75
    assert business["net_eur_mo"] == 3_450


def test_es23_unparsed_sourced_hourly_cost_becomes_open_item_not_default() -> None:
    model = {
        "conversation_id": "C1",
        "facts": [
            _km_fact("Process about 850 purchase requisitions per month.", metric={"kind": "monthly_volume", "value": 850}),
            _km_fact("Current process requires roughly 95 hours per month in the repeatable core.", metric={"kind": "automatable_hours_mo", "value": 95}),
            _km_fact(
                "Finance said loaded staff cost is forty-eight euros an hour.",
            ),
        ],
        "stated_requirements": [
            _km_fact(
                "Cut manual checking time from 95 hours per month to under 20 hours.",
                origin="USER_INPUT",
                metric={"kind": "target_remaining_hours_mo", "value": 20},
            ),
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
    skeleton = assemble_from_knowledge([model], opportunity_id="OPP-UNPARSED")
    assert "loaded_hourly_cost_eur" in skeleton["engine_inputs"]["unresolved_fields"]
    business = run_engines(skeleton, overrides={})["business_case"]
    assert business["inputs"]["loaded_hourly_cost_eur"] == 0
    assert business["inputs"]["loaded_hourly_cost_eur"] != 45


def test_es28_engine_derived_numbers_are_allowed_without_manual_variants() -> None:
    model = {
        "conversation_id": "C1",
        "facts": [
            _km_fact("Process about 850 purchase requisitions per month.", metric={"kind": "monthly_volume", "value": 850}),
            _km_fact("Current process requires roughly 95 hours per month in the repeatable core.", metric={"kind": "automatable_hours_mo", "value": 95}),
            _km_fact(
                "Cut manual checking time from 95 hours per month to under 20 hours.",
                origin="USER_INPUT",
                metric={"kind": "target_remaining_hours_mo", "value": 20},
            ),
            _km_fact("Loaded cost is EUR 48 per hour.", metric={"kind": "loaded_hourly_cost_eur", "value": 48}),
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
        opportunity_id="OPP-GUARD",
        title_hint="Purchase Requisition Approval",
        use_llm=False,
    )
    allowed = allowed_customer_numbers(framework)
    for token in ("75", "3600", "3450", "78.9", "79"):
        assert token in allowed
    ch9 = next(ch for ch in framework["chapters"] if str(ch.get("chapter_id")) == "9")
    assert lint_numbers(framework, _flatten_customer_text(ch9)) == []
