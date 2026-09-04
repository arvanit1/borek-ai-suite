"""Load the dummy, versioned Borek corpus used by AT-59 retrieval."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from services.borek_rag.models import Corpus, CorpusFact, FactKind, SourceCitation

_DATA_PATH = Path(__file__).resolve().parent / "data" / "borek_corpus_v1.json"
FACT_KINDS = ("service", "pricing", "staffing", "reference")
ALLOWED_CORPUS_OWNERS = frozenset({"Commercial", "Sales Ops"})
_REQUIRED_DOCUMENT_TYPES = {
    "pricing": "rate_card",
    "staffing": "staffing_profile",
    "service": "service_definition",
    "reference": "reference",
}
_STRUCTURED_AMOUNT = re.compile(r"^\d+(?:\.\d{1,2})?$")
_STRUCTURED_FTE = re.compile(r"^\d+(?:\.\d{1,2})?$")


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Corpus field '{key}' must be a non-empty string.")
    return value.strip()


def structured_pricing_payload(payload: dict[str, Any]) -> bool:
    amount = payload.get("amount")
    currency = payload.get("currency")
    unit = payload.get("unit")
    return (
        isinstance(amount, str)
        and bool(_STRUCTURED_AMOUNT.fullmatch(amount.strip()))
        and isinstance(currency, str)
        and bool(currency.strip())
        and isinstance(unit, str)
        and bool(unit.strip())
        and isinstance(payload.get("indicative"), bool)
    )


def _require_structured_payload(
    *,
    kind: FactKind,
    document_type: str,
    payload: dict[str, Any],
    fact_id: str,
) -> None:
    expected_type = _REQUIRED_DOCUMENT_TYPES[kind]
    if document_type != expected_type:
        raise ValueError(
            f"Fact {fact_id} kind '{kind}' must live on a '{expected_type}' document."
        )
    if kind == "pricing":
        if not structured_pricing_payload(payload):
            raise ValueError(
                f"Pricing fact {fact_id} must be a structured rate-card row "
                "(amount, currency, unit, indicative). Free-text prices are rejected."
            )
        return
    if kind == "staffing":
        headcount = payload.get("headcount")
        total_fte = payload.get("total_fte")
        if not isinstance(headcount, int) or headcount < 1:
            raise ValueError(f"Staffing fact {fact_id} must include a positive headcount.")
        if not isinstance(total_fte, str) or not _STRUCTURED_FTE.fullmatch(total_fte.strip()):
            raise ValueError(f"Staffing fact {fact_id} must include a structured total_fte.")
        return
    if kind == "service" and not str(payload.get("service_key") or "").strip():
        raise ValueError(f"Service fact {fact_id} must include a structured service_key.")
    if kind == "reference" and not str(payload.get("pattern") or "").strip():
        raise ValueError(f"Reference fact {fact_id} must include a structured pattern.")


def _require_kind(value: Any) -> FactKind:
    if value not in FACT_KINDS:
        raise ValueError(
            "Fact kind must be 'service', 'pricing', 'staffing', or 'reference'."
        )
    return value


def bundled_corpus_mapping() -> dict[str, Any]:
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Corpus root must be an object.")
    return raw


def corpus_from_mapping(raw: dict[str, Any]) -> Corpus:
    if not isinstance(raw, dict):
        raise ValueError("Corpus root must be an object.")

    corpus_id = _require_str(raw, "corpus_id")
    corpus_version = _require_str(raw, "corpus_version")
    schema_version = _require_str(raw, "schema_version")
    classification = _require_str(raw, "classification")
    owner_value = raw.get("owner")
    owner = (
        owner_value.strip()
        if isinstance(owner_value, str) and owner_value.strip()
        else "Commercial"
    )
    if owner not in ALLOWED_CORPUS_OWNERS:
        raise ValueError("Corpus owner must be 'Commercial' or 'Sales Ops'.")
    documents = raw.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("Corpus must contain at least one document.")

    facts: list[CorpusFact] = []
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("Each corpus document must be an object.")
        document_id = _require_str(document, "document_id")
        document_type = _require_str(document, "document_type")
        document_version = _require_str(document, "version")
        document_class = _require_str(document, "classification")
        effective_from = _require_str(document, "effective_from")
        effective_to = _require_str(document, "effective_to")
        raw_facts = document.get("facts")
        if not isinstance(raw_facts, list):
            raise ValueError(f"Document {document_id} facts must be a list.")
        for item in raw_facts:
            if not isinstance(item, dict):
                raise ValueError(f"Document {document_id} contains a non-object fact.")
            required = item.get("required_terms") or []
            optional = item.get("optional_terms") or []
            if not isinstance(required, list) or not required:
                raise ValueError(f"Fact {item.get('fact_id')} needs required_terms.")
            payload = item.get("payload")
            if not isinstance(payload, dict):
                raise ValueError(f"Fact {item.get('fact_id')} payload must be an object.")
            fact_id = _require_str(item, "fact_id")
            kind = _require_kind(item.get("kind"))
            _require_structured_payload(
                kind=kind,
                document_type=document_type,
                payload=payload,
                fact_id=fact_id,
            )
            source = SourceCitation(
                corpus_id=corpus_id,
                corpus_version=corpus_version,
                document_id=document_id,
                document_type=document_type,
                document_version=document_version,
                fact_id=fact_id,
                classification=document_class,
                effective_from=effective_from,
                effective_to=effective_to,
            )
            facts.append(
                CorpusFact(
                    fact_id=fact_id,
                    kind=kind,
                    service_key=_require_str(item, "service_key"),
                    query_key=_require_str(item, "query_key"),
                    required_terms=tuple(str(term).lower() for term in required),
                    optional_terms=tuple(str(term).lower() for term in optional),
                    statement=_require_str(item, "statement"),
                    payload=dict(payload),
                    source=source,
                )
            )

    return Corpus(
        corpus_id=corpus_id,
        corpus_version=corpus_version,
        schema_version=schema_version,
        classification=classification,
        owner=owner,
        facts=tuple(facts),
    )


def load_corpus(path: Path | None = None) -> Corpus:
    source_path = path or _DATA_PATH
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Corpus root must be an object.")
    return corpus_from_mapping(raw)


@lru_cache(maxsize=1)
def default_corpus() -> Corpus:
    return load_corpus()
