"""Deterministic retrieval over the dummy Borek corpus.

This is a production-shaped AT-59 spike: structured lookup with citations.
It never interpolates, never invents amounts, and returns unknown when the
corpus does not uniquely support the question.
"""

from __future__ import annotations

import re

from services.borek_rag.corpus import default_corpus, structured_pricing_payload
from services.borek_rag.models import Corpus, CorpusFact, RetrievalQuery, RetrievalResult

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)
_UNKNOWN = RetrievalResult(
    status="unknown",
    statement=None,
    payload=None,
    sources=(),
    reason="no_supported_fact",
)


def _normalize(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("3 way", "3-way").replace("three way", "three-way")
    return lowered


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(_normalize(text))}


def _contains_term(blob: str, term: str) -> bool:
    needle = term.lower()
    if " " in needle or "-" in needle:
        return needle in blob
    return any(token == needle or token.startswith(needle) for token in _tokens(blob))


def _matches(fact: CorpusFact, query: RetrievalQuery, blob: str) -> bool:
    if query.kind is not None and fact.kind != query.kind:
        return False
    if query.service_key is not None and fact.service_key != query.service_key:
        return False
    if query.query_key:
        return fact.query_key == query.query_key
    return all(_contains_term(blob, term) for term in fact.required_terms)


def retrieve(query: RetrievalQuery, *, corpus: Corpus | None = None) -> RetrievalResult:
    """Return a cited fact or unknown. Never guess."""
    active = corpus or default_corpus()
    blob = _normalize(query.text or "")
    if not blob.strip() and not query.query_key and not query.service_key:
        return _UNKNOWN
    matches = [fact for fact in active.facts if _matches(fact, query, blob)]

    if len(matches) != 1:
        reason = "ambiguous_facts" if len(matches) > 1 else "no_supported_fact"
        return RetrievalResult(
            status="unknown",
            statement=None,
            payload=None,
            sources=(),
            reason=reason,
        )

    fact = matches[0]
    if fact.kind == "pricing" and not structured_pricing_payload(fact.payload):
        return RetrievalResult(
            status="unknown",
            statement=None,
            payload=None,
            sources=(),
            reason="unstructured_pricing_fact",
        )
    return RetrievalResult(
        status="answered",
        statement=fact.statement,
        payload=dict(fact.payload),
        sources=(fact.source,),
        reason="supported_by_corpus",
    )
