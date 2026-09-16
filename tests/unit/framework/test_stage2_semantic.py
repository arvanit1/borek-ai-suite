"""Stage 2 FE-06–09 plus F-2/F-3/F-27/F-28 semantic invariants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.framework.assembly import derive_quality_inputs
from services.framework.business_case import compute_business_case
from services.framework.chapter_builder import _business_case_rows
from services.framework.chapter_validators.ch00_about import has_eight_decision_questions
from services.framework.chapter_validators.ch04_solution_tobe import validate as validate_ch04
from services.framework.chapter_validators.ch06_how_built import has_building_protection, validate as validate_ch06
from services.framework.pipeline import generate_customer_framework, run_engines
from services.framework.source_traceability import (
    AtomicTraceabilityError,
    attach_block_source_refs,
    convert_unsupported_block_claims,
)
from services.knowledge_model.entry_ids import ensure_knowledge_entry_ids


def _entry(statement: str, turn: int, **extra: object) -> dict:
    model = {
        "transcript_id": "transcript-1",
        "facts": [
            {
                "statement": statement,
                "origin": "SOURCE_FACT",
                "confidence": "high",
                "source_refs": [
                    {
                        "conversation_id": "C1",
                        "speaker_role": "operator",
                        "excerpt_pointer": f"turn:{turn}",
                    }
                ],
                **extra,
            }
        ],
    }
    ensure_knowledge_entry_ids(model)
    packed = model["facts"][0]
    packed["bucket"] = "facts"
    return packed


def _quality_entry(statement: str, bucket: str, turn: int = 1, **extra: object) -> dict:
    entry = {
        "statement": statement,
        "origin": "SOURCE_FACT",
        "confidence": "high",
        "bucket": bucket,
        "source_refs": [
            {
                "conversation_id": "C1",
                "speaker_role": "operator",
                "excerpt_pointer": f"turn:{turn}",
            }
        ],
    }
    entry.update(extra)
    return entry


def test_live_synthesis_cannot_skip_atomic_provenance() -> None:
    entry = _entry("AP must approve invoices.", 3)
    framework = {
        "generation_meta": {"llm_used": True},
        "chapters": [
            {
                "chapter_id": "2",
                "body": [{"block": "prose", "text": "AP must approve 12 invoices."}],
                "source_refs": [],
            }
        ],
    }

    with pytest.raises(AtomicTraceabilityError, match="cite Knowledge entry"):
        attach_block_source_refs(framework, [entry])


def test_f27_unrelated_number_cannot_ground_a_different_metric() -> None:
    hours = _entry("The team spends 310 hours per month on manual matching.", 1)
    hours["metric"] = {"kind": "automatable_hours_mo", "value": 310}
    sla = _entry("Response time target is 2 hours.", 2)
    sla["metric"] = {"kind": "target_remaining_hours_mo", "value": 2}
    framework = {
        "generation_meta": {},
        "chapters": [
            {
                "chapter_id": "3",
                "body": [
                    {
                        "block": "prose",
                        "text": "Target remaining work is 2 hours.",
                        "source_claims": [
                            {
                                "path": "/text",
                                "claim": "Target remaining work is 2 hours.",
                                "knowledge_entry_ids": [hours["entry_id"]],
                                "source_refs": [],
                            }
                        ],
                    }
                ],
                "source_refs": [],
            }
        ],
    }

    with pytest.raises(AtomicTraceabilityError, match="does not exactly match"):
        attach_block_source_refs(framework, [hours, sla])


def test_f28_identifiers_are_not_promoted_to_customer_open_items() -> None:
    framework = {
        "generation_meta": {"traceability_version": "atomic-v1"},
        "open_items": [],
        "chapters": [
            {
                "chapter_id": "11",
                "title": "Open points",
                "body": [{"block": "prose", "text": "Confirm OPP-061985 and 27880 before go-live."}],
            }
        ],
    }

    convert_unsupported_block_claims(framework, [])

    blob = str(framework["open_items"]) + str(framework["chapters"][0]["body"])
    assert "061985" not in blob
    assert "27880" not in blob


def test_fe08_sparse_negated_and_strong_evidence_change_scores() -> None:
    sparse = derive_quality_inputs(
        [_quality_entry("Invoices arrive by email.", "facts")],
        [],
        [],
        {},
    )
    negated = derive_quality_inputs(
        [
            _quality_entry("Mailbox access is not available.", "named_systems"),
            _quality_entry("Write access is pending approval.", "constraints"),
        ],
        [{"name": "Mailbox", "direction": "read", "status": "open_dependency"}],
        [],
        {},
    )
    strong = derive_quality_inputs(
        [
            _quality_entry("Invoices arrive by email.", "facts"),
            _quality_entry("The team wants automatic matching.", "stated_requirements"),
            _quality_entry("Volume is 3000 invoices per month.", "facts", metric={"kind": "monthly_volume", "value": 3000}),
            _quality_entry("Core work is 73 hours per month.", "facts", metric={"kind": "automatable_hours_mo", "value": 73}),
            _quality_entry("ERP is the system of record.", "named_systems"),
            _quality_entry("Match PO, receipt, and invoice.", "named_rules"),
            _quality_entry("Price variance is an exception.", "named_exceptions"),
            _quality_entry("AP clerks own the queue.", "people_and_roles"),
            _quality_entry("Data must stay in the EU for GDPR.", "constraints"),
            _quality_entry("Duplicate payments are the residual risk.", "risks"),
            _quality_entry("Sample invoices are available.", "facts"),
            _quality_entry("Success is measured against the 12-hour target.", "stated_requirements", metric={"kind": "target_remaining_hours_mo", "value": 12}),
        ],
        [
            {"name": "Mailbox", "direction": "read", "status": "available"},
            {"name": "ERP", "direction": "read_write", "status": "available"},
        ],
        [{"name": "Three-way match", "logic": "PO, GR, invoice"}],
        {"monthly_volume": 3000, "automatable_hours_mo": 73},
    )

    assert sparse["information_richness"] < strong["information_richness"]
    assert sparse["result_quality"] <= strong["result_quality"]
    assert negated["blocker_open_questions"] > 0
    assert negated["system_read_available"] is False
    assert strong["has_sample"] is True
    assert strong["business_case_complete"] is True
    assert strong["data_compliance_complete"] is True
    assert strong["feasibility_level"] >= sparse["feasibility_level"]


def test_fe09_missing_financial_basis_does_not_publish_config_defaults() -> None:
    result = compute_business_case(
        automatable_hours_mo=73,
        monthly_volume=3000,
        build_cost_eur=15000,
        archetype="system_to_system",
        allow_config_defaults=True,
    )
    assert result["grounded"] is False
    assert result["hours_saved_mo"] is None
    assert result["gross_eur_mo"] is None
    assert result["net_eur_mo"] is None
    assert result["run_cost_eur_mo"] is None
    rows = _business_case_rows(result, {"build_cost_eur": 15000}, "OPEN ITEM")
    blob = str(rows)
    assert "EUR 45" not in blob
    assert "2800" not in blob
    assert "OPEN ITEM" in blob

    skeleton = {
        "engine_inputs": {
            "automatable_hours_mo": 73,
            "monthly_volume": 3000,
            "unresolved_fields": [],
        },
        "open_items": [],
        "systems": [],
    }
    business = run_engines(skeleton, overrides={})["business_case"]
    assert business["grounded"] is False
    assert "45" not in str(_business_case_rows(business, {"build_cost_eur": 15000}, "OPEN ITEM"))


def test_f2_typed_eight_questions_do_not_need_english_phrases() -> None:
    chapter = {
        "body": [
            {
                "block": "bullets",
                "kind": "decision_questions",
                "items": [f"Decision {index}" for index in range(8)],
            }
        ]
    }
    assert has_eight_decision_questions(chapter)
    chapter["body"][0]["items"] = ["Decision 1"]
    assert not has_eight_decision_questions(chapter)


def test_f3_typed_today_vs_agent_and_building_blocks_do_not_need_keywords() -> None:
    chapter_4 = {
        "body": [
            {
                "block": "process_flow",
                "caption": "To-be process (stage 2)",
                "nodes": [
                    {"id": "n0", "label": "Intake", "kind": "system"},
                    {"id": "n1", "label": "Match", "kind": "agent"},
                ],
                "edges": [{"from": "n0", "to": "n1", "label": ""}],
            },
            {
                "block": "table",
                "kind": "today_vs_agent",
                "caption": "Comparison",
                "columns": ["As now", "With workflow"],
                "rows": [["Manual intake", "Extracted automatically"]],
            },
        ]
    }
    assert validate_ch04({}, chapter_4) == []

    chapter_6 = {
        "body": [
            {
                "block": "table",
                "kind": "building_blocks",
                "caption": "Components",
                "columns": ["Block", "Role", "Safeguard"],
                "rows": [["Inbox reader", "Intake", "Least-privilege access"]],
            },
            {
                "block": "ai_split",
                "used_for": ["Extract fields"],
                "not_used_for": ["Approve exceptions"],
            },
        ]
    }
    assert has_building_protection(chapter_6)
    issues = {issue.code for issue in validate_ch06({"systems": [{"name": "ERP"}]}, chapter_6)}
    assert "building_blocks" not in issues
    assert "building_protection" not in issues


def test_sparse_transcript_still_generates_without_invented_hourly_cost() -> None:
    model = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages"
            / "contracts"
            / "fixtures"
            / "knowledge_model.invoice_3way.json"
        ).read_text(encoding="utf-8")
    )
    for bucket in ("facts", "stated_requirements", "constraints"):
        model[bucket] = [
            entry
            for entry in model.get(bucket) or []
            if "EUR 45" not in str(entry.get("statement") or "")
            and "per hour" not in str(entry.get("statement") or "").lower()
        ]
    framework = generate_customer_framework(
        [model],
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides={"automatable_hours_mo": 73, "monthly_volume": 3000},
    )
    chapter_9 = next(chapter for chapter in framework["chapters"] if str(chapter.get("chapter_id")) == "9")
    blob = str(chapter_9["body"])
    assert "EUR 45" not in blob
    assert framework["business_case"]["grounded"] is False
