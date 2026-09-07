"""ES-39 — Borek company facts only through AT-59 retrieve. Never invent a price or headcount."""

from __future__ import annotations

import copy
from typing import Any, Callable

from services.borek_rag import RetrievalQuery, RetrievalResult, retrieve
from services.borek_rag.models import Corpus, SourceCitation

FACT_KINDS = ("service", "pricing", "staffing", "reference")
RetrieveFn = Callable[..., RetrievalResult]

_KIND_QUESTIONS = {
    "service": "What is the Borek service definition for {subject}?",
    "pricing": "What is the senior consultant day rate for {subject}?",
    "staffing": "What staffing and FTE do we have for {subject}?",
    "reference": "What reference delivery pattern do we use for {subject}?",
}


def query_text_from_parts(*parts: Any) -> str:
    texts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = str(part or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        texts.append(text)
    return " ".join(texts)


def query_text_from_opportunity(opportunity: dict[str, Any] | None) -> str:
    opportunity = opportunity or {}
    return query_text_from_parts(
        opportunity.get("opportunity_name"),
        opportunity.get("department"),
    )


def ground_company_facts(
    subject: str,
    *,
    retrieve_fn: RetrieveFn | None = None,
    corpus: Corpus | None = None,
) -> dict[str, Any]:
    """Retrieve service, pricing, staffing, and reference. Unique match only."""
    runner = retrieve_fn or retrieve
    subject_text = str(subject or "").strip()
    lookups: list[dict[str, Any]] = []
    service_key: str | None = None
    for kind in FACT_KINDS:
        text = _KIND_QUESTIONS[kind].format(subject=subject_text or "this opportunity")
        query = RetrievalQuery(text=text, kind=kind, service_key=service_key)
        result = runner(query, corpus=corpus)
        lookup = _serialize_lookup(kind=kind, query=query, result=result)
        lookups.append(lookup)
        if kind == "service" and result.status == "answered":
            payload = result.payload or {}
            key = str(payload.get("service_key") or "").strip()
            service_key = key or service_key
    return {
        "subject": subject_text,
        "lookups": lookups,
        "answered": [item for item in lookups if item["status"] == "answered"],
        "unknown": [item for item in lookups if item["status"] == "unknown"],
    }


def format_company_facts_for_prompt(grounding: dict[str, Any] | None) -> str:
    if not grounding or not grounding.get("lookups"):
        return ""
    lines = [
        "COMPANY_FACTS_BEGIN",
        "Borek company facts from in-process retrieve (AT-59). Unique match only.",
        "Do not invent a Borek price, day rate, list price, headcount, or FTE.",
        "If a kind is unknown, write an open_item with no number.",
        "Client conversation hours and volume are not company facts.",
        "ENGINE OUTPUTS build_cost_eur is an effort-model figure, not a Borek rate card.",
    ]
    for item in grounding.get("lookups") or []:
        kind = item.get("kind")
        if item.get("status") == "answered":
            lines.append(f"{kind}: answered")
            if item.get("statement"):
                lines.append(f"statement: {item['statement']}")
            if item.get("payload") is not None:
                lines.append(f"payload: {item['payload']}")
            for source in item.get("sources") or []:
                lines.append(
                    "cite: "
                    f"corpus_version={source.get('corpus_version')} "
                    f"document_id={source.get('document_id')} "
                    f"fact_id={source.get('fact_id')}"
                )
            continue
        lines.append(
            f"{kind}: unknown ({item.get('reason') or 'no_supported_fact'}). "
            "Open question. No number."
        )
    lines.append("COMPANY_FACTS_END")
    return "\n".join(lines)


def apply_company_facts_to_skeleton(
    skeleton: dict[str, Any],
    grounding: dict[str, Any] | None,
) -> dict[str, Any]:
    if not grounding:
        return skeleton
    updated = copy.deepcopy(skeleton)
    updated["company_facts"] = copy.deepcopy(grounding)
    open_items = list(updated.get("open_items") or [])
    open_items.extend(unknown_open_items(grounding))
    updated["open_items"] = _unique_open_items(open_items)
    return updated


def attach_company_facts_meta(
    framework: dict[str, Any],
    grounding: dict[str, Any] | None,
) -> dict[str, Any]:
    generation_meta = dict(framework.get("generation_meta") or {})
    generation_meta["company_facts"] = _meta_payload(grounding)
    framework["generation_meta"] = generation_meta
    return framework


def apply_company_facts_to_framework(
    framework: dict[str, Any],
    grounding: dict[str, Any] | None,
) -> dict[str, Any]:
    attach_company_facts_meta(framework, grounding)
    if not grounding:
        return framework
    open_items = list(framework.get("open_items") or [])
    open_items.extend(unknown_open_items(grounding))
    framework["open_items"] = _unique_open_items(open_items)
    return framework


def unknown_open_items(grounding: dict[str, Any] | None) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for lookup in (grounding or {}).get("unknown") or []:
        kind = str(lookup.get("kind") or "company_fact")
        reason = str(lookup.get("reason") or "no_supported_fact")
        items.append(
            {
                "description": (
                    f"Borek {kind} is not uniquely supported by the company corpus "
                    f"({reason}). Do not invent a number; confirm with Commercial."
                ),
                "item_type": "assumption",
                "owner": "Commercial",
                "consequence_if_different": (
                    "Company prices and headcount come only from retrieval. "
                    "A guessed EUR or FTE figure is not allowed."
                ),
            }
        )
    return items


def _serialize_lookup(*, kind: str, query: RetrievalQuery, result: RetrievalResult) -> dict[str, Any]:
    return {
        "kind": kind,
        "status": result.status,
        "reason": result.reason,
        "statement": result.statement,
        "payload": copy.deepcopy(result.payload) if result.payload is not None else None,
        "sources": [_serialize_source(source) for source in result.sources],
        "query": {
            "text": query.text,
            "kind": query.kind,
            "query_key": query.query_key,
            "service_key": query.service_key,
        },
    }


def _serialize_source(source: SourceCitation) -> dict[str, str]:
    return {
        "corpus_id": source.corpus_id,
        "corpus_version": source.corpus_version,
        "document_id": source.document_id,
        "document_type": source.document_type,
        "document_version": source.document_version,
        "fact_id": source.fact_id,
        "classification": source.classification,
        "effective_from": source.effective_from,
        "effective_to": source.effective_to,
    }


def _meta_payload(grounding: dict[str, Any] | None) -> dict[str, Any]:
    if not grounding:
        return {
            "applied": False,
            "source": "borek_rag.retrieve",
            "lookups": [],
            "answered": [],
            "unknown": [],
        }
    answered = list(grounding.get("answered") or [])
    return {
        "applied": bool(answered),
        "source": "borek_rag.retrieve",
        "subject": grounding.get("subject") or "",
        "lookups": copy.deepcopy(grounding.get("lookups") or []),
        "answered": copy.deepcopy(answered),
        "unknown": copy.deepcopy(grounding.get("unknown") or []),
    }


def _unique_open_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("description") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
