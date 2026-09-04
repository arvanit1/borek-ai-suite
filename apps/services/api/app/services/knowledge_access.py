"""Resolve the active AT-59 corpus from the store or the bundled dummy."""

from __future__ import annotations

from typing import Any

from services.borek_rag.corpus import default_corpus
from services.borek_rag.ingest import corpus_from_store_rows
from services.borek_rag.models import Corpus


def resolve_active_corpus(store: Any) -> Corpus:
    rows = store.list_approved_knowledge_facts()
    if rows:
        return corpus_from_store_rows(rows)
    return default_corpus()


def describe_active_corpus(store: Any) -> dict[str, Any]:
    meta = store.get_approved_knowledge_corpus()
    if meta is not None:
        return meta
    corpus = default_corpus()
    return {
        "source": "bundled_dummy",
        "corpus_key": corpus.corpus_id,
        "version": corpus.corpus_version,
        "status": "approved",
        "owner": corpus.owner,
        "classification": corpus.classification,
        "document_count": len({fact.source.document_id for fact in corpus.facts}),
        "fact_count": len(corpus.facts),
        "fact_kinds": sorted({fact.kind for fact in corpus.facts}),
    }
