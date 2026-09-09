"""ES-39 — Borek company facts only through AT-59 retrieve. Never invent a price or headcount."""

from __future__ import annotations

import copy
import re
from typing import Any, Callable

from services.borek_rag import RetrievalQuery, RetrievalResult, retrieve
from services.borek_rag.identity import (
    demo_provenance_marker,
    is_demo_corpus,
    live_provenance_marker,
)
from services.borek_rag.models import Corpus, SourceCitation

FACT_KINDS = ("service", "pricing", "staffing", "reference")
COMPANY_FACT_ORIGIN = "company_corpus"
COMPANY_FACT_CAPTION = "Borek company facts (retrieved)"
_CHAPTER_FOR_KIND = {
    "service": "4",
    "reference": "4",
    "pricing": "9",
    "staffing": "10",
}
RetrieveFn = Callable[..., RetrievalResult]

_KIND_QUESTIONS = {
    "service": "What is the Borek service definition for {subject}?",
    "pricing": "What is the senior consultant day rate for {subject}?",
    "staffing": "What staffing and FTE do we have for {subject}?",
    "reference": "What reference delivery pattern do we use for {subject}?",
}
# Rate-card shaped figures only. Client savings such as "EUR 120,000 saved" are
# conversation facts, not Borek prices the system originated.
_RATE_CARD_AMOUNT_RE = re.compile(
    r"(?:EUR|USD|GBP|CHF|€)\s*(\d[\d,]*(?:\.\d{1,2})?)\s*"
    r"(?:/\s*(?:day|hour|month)|per\s+(?:day|hour|month)|day rate)"
    r"|(?:day rate|list price)[^\d]{0,40}(?:EUR|USD|GBP|CHF|€)\s*(\d[\d,]*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)


class UngroundedPriceError(ValueError):
    """A commercial figure appeared without ES-39 rate-card provenance."""


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
        if kind == "pricing" and lookup["status"] == "answered" and not has_live_provenance(lookup):
            lookup["status"] = "unknown"
            lookup["reason"] = "missing_rate_card_provenance"
            lookup["statement"] = None
            lookup["payload"] = None
            lookup["sources"] = []
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


def apply_company_facts_to_chapters(
    framework: dict[str, Any],
    grounding: dict[str, Any] | None,
) -> dict[str, Any]:
    """Write answered retrieve facts into chapters 4/9/10 with corpus citations."""
    blocks = _chapter_blocks(grounding)
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        body = [
            block
            for block in (chapter.get("body") or [])
            if not (isinstance(block, dict) and block.get("origin") == COMPANY_FACT_ORIGIN)
        ]
        extra = blocks.get(str(chapter.get("chapter_id")))
        if extra is not None:
            body.append(copy.deepcopy(extra))
        chapter["body"] = body
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
    apply_company_facts_to_chapters(framework, grounding)
    return framework


def _chapter_blocks(grounding: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows_by_chapter: dict[str, list[dict[str, str]]] = {}
    for lookup in (grounding or {}).get("answered") or []:
        if lookup.get("status") != "answered":
            continue
        chapter_id = _CHAPTER_FOR_KIND.get(str(lookup.get("kind") or ""))
        row = _row_for_lookup(lookup)
        if not chapter_id or row is None:
            continue
        rows_by_chapter.setdefault(chapter_id, []).append(row)
    return {
        chapter_id: {
            "block": "kv_rows",
            "caption": COMPANY_FACT_CAPTION,
            "origin": COMPANY_FACT_ORIGIN,
            "rows": rows,
        }
        for chapter_id, rows in rows_by_chapter.items()
        if rows
    }


def format_company_fact_line(lookup: dict[str, Any]) -> str | None:
    """Customer-facing line for one answered retrieve fact, including corpus citation."""
    row = _row_for_lookup(lookup)
    if row is None:
        return None
    return f"{row['label']}: {row['value']}"


def _row_for_lookup(lookup: dict[str, Any]) -> dict[str, str] | None:
    kind = str(lookup.get("kind") or "")
    cite = _citation_text(lookup.get("sources") or [])
    if not cite:
        return None
    payload = lookup.get("payload") or {}
    statement = str(lookup.get("statement") or "").strip()
    if kind == "pricing":
        amount = payload.get("amount")
        currency = payload.get("currency")
        unit = payload.get("unit")
        if amount is None or not currency or not unit:
            return None
        value = f"{currency} {amount} / {unit}"
        if payload.get("indicative") is True:
            value += " (indicative)"
        return {"label": "Borek rate card", "value": f"{value}. {cite}"}
    if kind == "staffing":
        headcount = payload.get("headcount")
        fte = payload.get("total_fte")
        if headcount is None:
            return None
        value = f"{headcount} people"
        if fte is not None and str(fte).strip():
            value += f" / {fte} FTE"
        return {"label": "Borek staffing", "value": f"{value}. {cite}"}
    if kind == "service":
        text = statement or str(payload.get("name") or "").strip()
        if not text:
            return None
        return {"label": "Borek service", "value": f"{text} {cite}"}
    if kind == "reference":
        text = statement or str(payload.get("pattern") or "").strip()
        if not text:
            return None
        return {"label": "Borek reference", "value": f"{text} {cite}"}
    return None


def _citation_text(sources: list[Any]) -> str:
    if not sources or not isinstance(sources[0], dict):
        return ""
    source = sources[0]
    if is_demo_corpus(str(source.get("corpus_id") or "")):
        return ""
    if str(source.get("provenance_marker") or "").strip() == demo_provenance_marker():
        return ""
    corpus_version = str(source.get("corpus_version") or "").strip()
    document_id = str(source.get("document_id") or "").strip()
    fact_id = str(source.get("fact_id") or "").strip()
    if not (corpus_version and document_id and fact_id):
        return ""
    return f"(corpus {corpus_version}, {document_id}, {fact_id})"


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
    marker = str(source.provenance_marker or "").strip() or live_provenance_marker()
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
        "provenance_marker": marker,
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


def has_live_provenance(lookup: dict[str, Any]) -> bool:
    """True when an answered fact cites the live corpus, never the demo pack."""
    if str(lookup.get("status") or "") != "answered":
        return False
    sources = lookup.get("sources") or []
    if not sources or not isinstance(sources[0], dict):
        return False
    source = sources[0]
    if is_demo_corpus(str(source.get("corpus_id") or "")):
        return False
    marker = str(source.get("provenance_marker") or "").strip()
    if marker == demo_provenance_marker():
        return False
    return bool(
        str(source.get("corpus_version") or "").strip()
        and str(source.get("document_id") or "").strip()
        and str(source.get("fact_id") or "").strip()
        and (not marker or marker == live_provenance_marker())
    )


def live_answered_lookups(
    grounding: dict[str, Any] | None,
    *,
    kinds: set[str] | None = None,
    include_pricing: bool = True,
) -> list[dict[str, Any]]:
    answered: list[dict[str, Any]] = []
    for lookup in (grounding or {}).get("answered") or (grounding or {}).get("lookups") or []:
        kind = str(lookup.get("kind") or "")
        if kinds is not None and kind not in kinds:
            continue
        if kind == "pricing" and not include_pricing:
            continue
        if not has_live_provenance(lookup):
            continue
        answered.append(lookup)
    return answered


def grounded_price_amounts(grounding: dict[str, Any] | None) -> set[str]:
    amounts: set[str] = set()
    for lookup in live_answered_lookups(grounding, kinds={"pricing"}):
        payload = lookup.get("payload") or {}
        amount = payload.get("amount")
        if amount is None:
            continue
        amounts.add(_normalize_amount(amount))
    return amounts


def grounded_pricing_figures(grounding: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every live price with its rate-card provenance. Missing provenance is omitted."""
    figures: list[dict[str, Any]] = []
    for lookup in live_answered_lookups(grounding, kinds={"pricing"}):
        payload = lookup.get("payload") or {}
        source = (lookup.get("sources") or [{}])[0]
        amount = payload.get("amount")
        currency = payload.get("currency")
        unit = payload.get("unit")
        if amount is None or not currency or not unit:
            continue
        if payload.get("indicative") is not True:
            raise UngroundedPriceError(
                "A retrieved price is missing the indicative label required by D5."
            )
        figures.append(
            {
                "amount": str(amount),
                "currency": str(currency),
                "unit": str(unit),
                "indicative": True,
                "statement": lookup.get("statement"),
                "payload": copy.deepcopy(payload),
                "provenance": {
                    "corpus_id": source.get("corpus_id"),
                    "corpus_version": source.get("corpus_version"),
                    "document_id": source.get("document_id"),
                    "document_type": source.get("document_type"),
                    "document_version": source.get("document_version"),
                    "fact_id": source.get("fact_id"),
                    "marker": source.get("provenance_marker") or live_provenance_marker(),
                },
            }
        )
    return figures


def rate_card_amounts_in_text(text: str) -> set[str]:
    amounts: set[str] = set()
    for match in _RATE_CARD_AMOUNT_RE.finditer(text or ""):
        raw = next((group for group in match.groups() if group), None)
        if raw:
            amounts.add(_normalize_amount(raw))
    return amounts


def refuse_ungrounded_prices(
    *,
    text: str,
    grounding: dict[str, Any] | None,
    allow_prices: bool,
) -> None:
    """Refuse a Borek rate-card figure that retrieval did not cite. Never soften it."""
    amounts = rate_card_amounts_in_text(text)
    if not amounts:
        return
    if not allow_prices:
        found = ", ".join(sorted(amounts))
        raise UngroundedPriceError(
            f"Prices are not permitted in this payload ({found}). "
            "They are not labelled indicative as a workaround."
        )
    grounded = grounded_price_amounts(grounding)
    missing = sorted(amount for amount in amounts if amount not in grounded)
    if missing:
        raise UngroundedPriceError(
            "Ungrounded price refused: "
            + ", ".join(missing)
            + ". Every figure must carry ES-39 rate-card provenance."
        )


def _normalize_amount(value: Any) -> str:
    token = str(value).replace(",", "").strip()
    if token.endswith(".0"):
        token = token[:-2]
    if token.endswith(".00"):
        token = token[:-3]
    try:
        number = float(token)
    except ValueError:
        return token
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")
