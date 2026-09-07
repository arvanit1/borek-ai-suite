"""ES-39 — Borek company facts only through retrieve; never invent price or headcount."""

from __future__ import annotations

import json
from pathlib import Path

from services.borek_rag import RetrievalResult, retrieve
from services.framework.company_facts import (
    apply_company_facts_to_skeleton,
    format_company_facts_for_prompt,
    ground_company_facts,
)
from services.framework.pipeline import generate_customer_framework

FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "fixtures"


def _invoice_models() -> tuple[list[dict], dict]:
    model = json.loads((FIXTURES / "knowledge_model.invoice_3way.json").read_text(encoding="utf-8"))
    overrides = json.loads((FIXTURES / "engine_overrides.invoice_3way.json").read_text(encoding="utf-8"))
    return [model], overrides


def test_invoice_retrieve_answers_dummy_rate_card_with_citations() -> None:
    grounding = ground_company_facts("Invoice 3-Way Match")
    by_kind = {item["kind"]: item for item in grounding["lookups"]}
    pricing = by_kind["pricing"]
    staffing = by_kind["staffing"]
    assert pricing["status"] == "answered"
    assert pricing["payload"]["amount"] == "1250.00"
    assert pricing["payload"]["currency"] == "EUR"
    assert pricing["payload"]["unit"] == "day"
    assert pricing["payload"]["indicative"] is True
    assert pricing["sources"][0]["corpus_version"] == "2026.09.03"
    assert pricing["sources"][0]["document_id"] == "RC-DUMMY-2026-Q3"
    assert pricing["sources"][0]["fact_id"] == "price.invoice-3way.senior-consultant.day-rate"
    assert staffing["payload"]["headcount"] == 4
    assert not grounding["unknown"]


def test_unknown_retrieve_is_open_question_with_no_invented_number() -> None:
    grounding = ground_company_facts("Warehouse pallet labeling")
    assert grounding["answered"] == []
    assert {item["kind"] for item in grounding["unknown"]} == {
        "service",
        "pricing",
        "staffing",
        "reference",
    }
    assert all(item["reason"] in {"no_supported_fact", "ambiguous_facts"} for item in grounding["unknown"])
    prompt = format_company_facts_for_prompt(grounding)
    assert "No number" in prompt
    assert "1250" not in prompt
    skeleton = apply_company_facts_to_skeleton({"open_items": []}, grounding)
    descriptions = " ".join(item["description"] for item in skeleton["open_items"])
    assert "Do not invent a number" in descriptions
    assert "1250" not in descriptions
    assert "headcount" not in json.dumps(grounding["unknown"])


def test_unstructured_pricing_reason_stays_unknown() -> None:
    def retrieve_fn(query, *, corpus=None):
        if query.kind == "pricing":
            return RetrievalResult(
                status="unknown",
                statement=None,
                payload=None,
                sources=(),
                reason="unstructured_pricing_fact",
            )
        return retrieve(query, corpus=corpus)

    grounding = ground_company_facts("Invoice 3-Way Match", retrieve_fn=retrieve_fn)
    pricing = next(item for item in grounding["lookups"] if item["kind"] == "pricing")
    assert pricing["status"] == "unknown"
    assert pricing["reason"] == "unstructured_pricing_fact"
    assert pricing["payload"] is None


def test_generate_framework_cites_answered_company_facts() -> None:
    models, overrides = _invoice_models()
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    meta = framework["generation_meta"]["company_facts"]
    pricing = next(item for item in meta["lookups"] if item["kind"] == "pricing")
    assert meta["source"] == "borek_rag.retrieve"
    assert meta["applied"] is True
    assert pricing["payload"]["amount"] == "1250.00"
    assert pricing["sources"][0]["corpus_version"] == "2026.09.03"
    assert pricing["sources"][0]["fact_id"] == "price.invoice-3way.senior-consultant.day-rate"
    assert not any("Do not invent a number" in item["description"] for item in framework["open_items"])


def test_generate_framework_unknown_company_facts_add_open_items() -> None:
    models, overrides = _invoice_models()
    grounding = ground_company_facts("Warehouse pallet labeling")
    framework = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
        company_facts=grounding,
    )
    meta = framework["generation_meta"]["company_facts"]
    assert meta["applied"] is False
    assert {item["kind"] for item in meta["unknown"]} == {"service", "pricing", "staffing", "reference"}
    descriptions = " ".join(item["description"] for item in framework["open_items"])
    assert "Borek pricing is not uniquely supported" in descriptions
    assert "Borek staffing is not uniquely supported" in descriptions
    dumped = json.dumps(framework["generation_meta"]["company_facts"])
    assert "1250" not in dumped
    assert '"headcount": 4' not in dumped


def test_synthesis_prompt_includes_company_facts_and_forbids_invention() -> None:
    seen: dict[str, str] = {}
    models, overrides = _invoice_models()
    base = generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=False,
        engine_overrides=overrides,
    )
    draft = {
        "title": base["title"],
        "department": base["department"],
        "cover": {
            "tagline": str(base["cover"].get("tagline") or "Customer report"),
            "sources_line": str(base["cover"].get("sources_line") or "C1"),
            "how_produced": str(base["cover"].get("how_produced") or "deterministic"),
        },
        "open_items": base["open_items"],
        "kpis": base["kpis"],
        "systems": base["systems"],
        "rules": base["rules"],
        "exceptions": base["exceptions"],
        "access_needs": base["access_needs"],
        "chapters": base["chapters"],
    }

    def capture(system: str, user: str, schema: dict) -> dict:
        seen["user"] = user
        return draft

    generate_customer_framework(
        models,
        opportunity_id="OPP-142",
        title_hint="Invoice 3-Way Match",
        use_llm=True,
        complete=capture,
        engine_overrides=overrides,
    )
    assert "COMPANY_FACTS_BEGIN" in seen["user"]
    assert "Do not invent a Borek price" in seen["user"]
    assert "1250.00" in seen["user"]
    assert "corpus_version=2026.09.03" in seen["user"]
