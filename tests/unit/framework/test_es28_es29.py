"""ES-28 unsourced claims become open items; ES-29 two processes are not merged."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.framework.cross_chapter_rules import MultiProcessError, enforce_cross_chapter_rules, flag_multi_process
from services.framework.guardrails import convert_unsourced_claims
from services.framework.pipeline import generate_customer_framework
from services.framework.process_scope import MAX_SCOPE_ATTEMPTS, PROMPT_VERSION, enforce_semantic_process_scope
from services.framework.source_traceability import convert_unsupported_block_claims
from services.observability.llm_logger import STAGE_PROCESS_SCOPE, clear_generation_jobs, jobs_for_opportunity

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


def _models() -> tuple[list[dict], dict]:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    return [model], overrides


def test_es28_unsourced_number_is_converted_not_accepted() -> None:
    models, overrides = _models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    framework["chapters"][1]["body"].append({"block": "prose", "text": "An invented share is 61 percent."})
    convert_unsourced_claims(framework)
    assert any("61" in str(item.get("description", "")) for item in framework["open_items"])
    assert "61" not in str(framework["chapters"][1]["body"])
    assert any("open item" in str(block).lower() for block in framework["chapters"][1]["body"])


def test_es28_does_not_split_thousands_grouped_engine_numbers() -> None:
    models, overrides = _models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    framework["chapters"][9]["body"].append(
        {"block": "prose", "text": "Build cost EUR 15,000. An invented share is 61 percent."}
    )
    convert_unsourced_claims(framework)
    blob = str(framework["chapters"][9]["body"])
    assert "15,000" in blob
    assert "an open item,000" not in blob
    assert "61" not in blob


def test_es29_two_opportunity_ids_are_flagged_not_merged() -> None:
    models, overrides = _models()
    other = copy.deepcopy(models[0])
    other["opportunity_id"] = "OPP-999"
    other["conversation_id"] = "C9"
    with pytest.raises(MultiProcessError) as exc_info:
        generate_customer_framework(
            [models[0], other],
            opportunity_id="OPP-142",
            title_hint="Invoice 3-Way Match",
            use_llm=False,
            engine_overrides=overrides,
        )
    assert "not merged" in str(exc_info.value.user_message).lower()


def test_es28_mismatched_source_ref_is_converted_to_open_item() -> None:
    models, overrides = _models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    entries = framework.get("source_entries") or []
    wrong_ref = entries[0]["source_refs"][0]
    framework["chapters"][4]["body"].append(
        {
            "block": "prose",
            "text": "The workflow autonomously approves all invoices.",
            "source_refs": [wrong_ref],
        }
    )
    convert_unsupported_block_claims(framework, framework.get("source_entries") or [])
    assert any(
        "autonomously approves all invoices" in str(item.get("description", ""))
        for item in framework.get("open_items") or []
    )
    assert "autonomously approves all invoices" not in str(framework["chapters"][4]["body"])
    enforce_cross_chapter_rules(framework, framework.get("source_entries") or [])


def test_es28_claim_without_any_source_ref_is_converted_to_open_item() -> None:
    models, overrides = _models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    framework["chapters"][4]["body"].append(
        {"block": "prose", "text": "The workflow autonomously selects every supplier."}
    )
    convert_unsupported_block_claims(framework, framework.get("source_entries") or [])
    assert any(
        "no cited conversation excerpt" in str(item.get("description", ""))
        for item in framework.get("open_items") or []
    )
    assert "autonomously selects every supplier" not in str(framework["chapters"][4]["body"])
    enforce_cross_chapter_rules(framework, framework.get("source_entries") or [])


def test_es28_unnumbered_rule_table_without_source_ref_becomes_open_item() -> None:
    """ES-28 applies to rules and claims even when they contain no number."""
    models, overrides = _models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    framework["chapters"][4]["body"].append(
        {
            "block": "table",
            "caption": "Unverified rule",
            "columns": ["Rule", "Handling"],
            "rows": [["Supplier exception", "Release every new supplier automatically"]],
        }
    )

    convert_unsupported_block_claims(framework, framework.get("source_entries") or [])

    assert any(
        "Release every new supplier automatically" in str(item.get("description", ""))
        for item in framework.get("open_items") or []
    )
    assert "Release every new supplier automatically" not in str(framework["chapters"][4]["body"])


def test_es29_two_processes_same_opportunity_are_flagged() -> None:
    models, overrides = _models()
    dual = copy.deepcopy(models[0])
    dual["facts"].append(
        {
            "statement": "Employees submit 300 expense reports in Concur and managers approve them by hand.",
            "source_refs": [{"conversation_id": "C6", "speaker_role": "Jordan", "excerpt_pointer": "turn:9"}],
        }
    )
    with pytest.raises(MultiProcessError) as exc_info:
        generate_customer_framework(
            [dual],
            opportunity_id="OPP-142",
            title_hint="Invoice 3-Way Match",
            use_llm=False,
            engine_overrides=overrides,
        )
    assert "more than one process" in str(exc_info.value.user_message).lower()


def test_es29_generic_distinct_processes_are_flagged() -> None:
    model = {
        "opportunity_id": "OPP-142",
        "facts": [
            {"statement": "The team handles refund requests from the customer portal."},
            {"statement": "IT resets passwords after identity checks."},
        ],
    }
    with pytest.raises(MultiProcessError):
        flag_multi_process([model], opportunity_id="OPP-142")


def test_es29_semantic_gate_blocks_multiple_sourced_processes() -> None:
    models, _ = _models()
    ref = models[0]["facts"][0]["source_refs"][0]
    calls = {"count": 0}

    def complete(system: str, user: str, schema: dict) -> dict:
        calls["count"] += 1
        assert PROMPT_VERSION in system
        assert "<knowledge_entries>" in user
        if calls["count"] > 1:
            assert "RETRY" in user
            assert "Invoice matching" in user
        return {
            "decision": "multiple",
            "processes": [
                {"label": "Invoice matching", "source_refs": [ref]},
                {"label": "Expense approval", "source_refs": [ref]},
            ],
        }

    with pytest.raises(MultiProcessError, match="not merged"):
        enforce_semantic_process_scope(models, opportunity_id="OPP-142", complete=complete)
    assert calls["count"] == MAX_SCOPE_ATTEMPTS


def test_es29_semantic_gate_fails_closed_when_uncertain() -> None:
    models, _ = _models()
    ref = models[0]["facts"][0]["source_refs"][0]

    with pytest.raises(MultiProcessError, match="not confirmed"):
        enforce_semantic_process_scope(
            models,
            opportunity_id="OPP-142",
            complete=lambda _system, _user, _schema: {
                "decision": "uncertain",
                "processes": [{"label": "Unclear scope", "source_refs": [ref]}],
            },
        )


def test_es29_semantic_gate_accepts_one_sourced_process() -> None:
    models, _ = _models()
    ref = models[0]["facts"][0]["source_refs"][0]
    result = enforce_semantic_process_scope(
        models,
        opportunity_id="OPP-142",
        complete=lambda _system, _user, _schema: {
            "decision": "single",
            "processes": [{"label": "Invoice matching", "source_refs": [ref]}],
        },
    )
    assert result["decision"] == "single"


def test_es29_semantic_gate_logs_the_live_call(monkeypatch: pytest.MonkeyPatch) -> None:
    models, _ = _models()
    ref = models[0]["facts"][0]["source_refs"][0]
    clear_generation_jobs()
    monkeypatch.setattr(
        "services.framework.process_scope.structured_complete",
        lambda *_args, **_kwargs: {
            "decision": "single",
            "processes": [{"label": "Invoice matching", "source_refs": [ref]}],
        },
    )
    enforce_semantic_process_scope(models, opportunity_id="OPP-142")
    jobs = jobs_for_opportunity("OPP-142", stages=[STAGE_PROCESS_SCOPE])
    assert len(jobs) == 1
    assert jobs[0]["status"] == "success"
    assert jobs[0]["prompt_version"] == PROMPT_VERSION


def test_es29_semantic_gate_reprompts_related_subprocesses_into_one() -> None:
    models, _ = _models()
    ref = models[0]["facts"][0]["source_refs"][0]
    users: list[str] = []

    def complete(system: str, user: str, schema: dict) -> dict:
        users.append(user)
        if len(users) == 1:
            return {
                "decision": "multiple",
                "processes": [
                    {"label": "Customer support / Customer inquiry handling", "source_refs": [ref]},
                    {"label": "Sales reporting", "source_refs": [ref]},
                    {"label": "Rural customer engagement / Rural sales", "source_refs": [ref]},
                    {"label": "Inventory forecasting / Inventory management", "source_refs": [ref]},
                    {"label": "Rural distribution / Order fulfillment for rural customers", "source_refs": [ref]},
                    {"label": "Urban customer engagement / Urban sales", "source_refs": [ref]},
                ],
            }
        return {
            "decision": "single",
            "processes": [
                {
                    "label": "Rural and urban sales operations",
                    "source_refs": [ref],
                }
            ],
        }

    result = enforce_semantic_process_scope(models, opportunity_id="OPP-142", complete=complete)
    assert result["decision"] == "single"
    assert len(result["processes"]) == 1
    assert len(users) == 2
    assert "RETRY" in users[1]
    assert "Rural customer engagement / Rural sales" in users[1]
    assert "independently automatable" in users[1]


def test_es29_semantic_gate_exhausts_retries_then_fails_closed() -> None:
    models, _ = _models()
    ref = models[0]["facts"][0]["source_refs"][0]
    calls = {"count": 0}

    def complete(_system: str, _user: str, _schema: dict) -> dict:
        calls["count"] += 1
        return {
            "decision": "uncertain",
            "processes": [{"label": "Unclear scope", "source_refs": [ref]}],
        }

    with pytest.raises(MultiProcessError, match="not confirmed"):
        enforce_semantic_process_scope(models, opportunity_id="OPP-142", complete=complete)
    assert calls["count"] == MAX_SCOPE_ATTEMPTS


def test_es29_semantic_gate_retries_invalid_payload_then_accepts_single() -> None:
    models, _ = _models()
    ref = models[0]["facts"][0]["source_refs"][0]
    calls = {"count": 0}

    def complete(_system: str, user: str, _schema: dict) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            return {"decision": "single", "processes": []}
        assert "RETRY" in user
        return {
            "decision": "single",
            "processes": [{"label": "Invoice matching", "source_refs": [ref]}],
        }

    result = enforce_semantic_process_scope(models, opportunity_id="OPP-142", complete=complete)
    assert result["decision"] == "single"
    assert calls["count"] == 2


def test_es28_chapter_zero_boilerplate_is_not_converted_to_open_item() -> None:
    models, overrides = _models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    ch0 = framework["chapters"][0]["body"]
    blob = str(ch0).lower()
    assert "false precision" in blob
    assert "traceable" in blob
    assert not any(
        "claim in chapter 0" in str(item.get("description", "")).lower()
        for item in framework.get("open_items") or []
    )
    assert not any(
        block.get("tone") == "open_item"
        for block in ch0
        if isinstance(block, dict)
    )
