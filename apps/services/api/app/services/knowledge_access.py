"""Resolve the active AT-59 live corpus from the store or the bundled seed."""

from __future__ import annotations

from typing import Any

from services.borek_rag.corpus import default_corpus
from services.borek_rag.identity import live_corpus_id
from services.borek_rag.ingest import corpus_from_store_rows
from services.borek_rag.models import Corpus


def _rows_for_corpus(store: Any, corpus_id: str) -> list[dict[str, Any]]:
    lister = getattr(store, "list_approved_knowledge_facts", None)
    if not callable(lister):
        return []
    return [
        row
        for row in lister()
        if str(row.get("corpus_key") or "").strip() == corpus_id
    ]


def resolve_active_corpus(store: Any, *, corpus_id: str | None = None) -> Corpus:
    """Live retrieval reads borek-internal only. Demo facts stay on borek-demo."""
    target = str(corpus_id or live_corpus_id()).strip() or live_corpus_id()
    rows = _rows_for_corpus(store, target)
    if rows:
        return corpus_from_store_rows(rows)
    if target == live_corpus_id():
        return default_corpus()
    raise ValueError(f"No approved facts for corpus '{target}'.")


def describe_active_corpus(store: Any) -> dict[str, Any]:
    rows = _rows_for_corpus(store, live_corpus_id())
    if rows:
        first = rows[0]
        return {
            "source": "store",
            "corpus_key": first["corpus_key"],
            "version": first["corpus_version"],
            "status": "approved",
            "owner": first["owner"],
            "classification": first.get("corpus_classification") or first["classification"],
            "document_count": len({row["document_key"] for row in rows}),
            "fact_count": len(rows),
            "fact_kinds": sorted({row["kind"] for row in rows}),
        }
    corpus = default_corpus()
    return {
        "source": "bundled",
        "corpus_key": corpus.corpus_id,
        "version": corpus.corpus_version,
        "status": "approved",
        "owner": corpus.owner,
        "classification": corpus.classification,
        "document_count": len({fact.source.document_id for fact in corpus.facts}),
        "fact_count": len(corpus.facts),
        "fact_kinds": sorted({fact.kind for fact in corpus.facts}),
    }
