"""Map a versioned Borek corpus onto the AT-59 store tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.borek_rag.corpus import FACT_KINDS, corpus_from_mapping
from services.borek_rag.models import Corpus, CorpusFact, FactKind, SourceCitation


@dataclass(frozen=True)
class PlannedFact:
    fact_key: str
    kind: FactKind
    service_key: str
    query_key: str
    statement: str
    payload: dict[str, Any]
    search_terms: tuple[str, ...]


@dataclass(frozen=True)
class PlannedDocument:
    document_key: str
    document_type: str
    source_uri: str
    source_version: str
    classification: str
    effective_from: str
    effective_to: str
    facts: tuple[PlannedFact, ...]


@dataclass(frozen=True)
class IngestPlan:
    corpus_key: str
    version: str
    owner: str
    classification: str
    schema_version: str
    documents: tuple[PlannedDocument, ...]

    @property
    def fact_count(self) -> int:
        return sum(len(document.facts) for document in self.documents)


def plan_ingest(raw: dict[str, Any]) -> IngestPlan:
    corpus = corpus_from_mapping(raw)
    documents: list[PlannedDocument] = []
    raw_documents = raw.get("documents")
    if not isinstance(raw_documents, list):
        raise ValueError("Corpus must contain at least one document.")
    for document in raw_documents:
        if not isinstance(document, dict):
            raise ValueError("Each corpus document must be an object.")
        document_id = str(document["document_id"]).strip()
        source_version = str(document["version"]).strip()
        facts = tuple(
            PlannedFact(
                fact_key=fact.fact_id,
                kind=fact.kind,
                service_key=fact.service_key,
                query_key=fact.query_key,
                statement=fact.statement,
                payload=dict(fact.payload),
                search_terms=fact.required_terms,
            )
            for fact in corpus.facts
            if fact.source.document_id == document_id
        )
        documents.append(
            PlannedDocument(
                document_key=document_id,
                document_type=str(document["document_type"]).strip(),
                source_uri=f"corpus://{corpus.corpus_id}/{document_id}@{source_version}",
                source_version=source_version,
                classification=str(document["classification"]).strip(),
                effective_from=str(document["effective_from"]).strip(),
                effective_to=str(document["effective_to"]).strip(),
                facts=facts,
            )
        )
    return IngestPlan(
        corpus_key=corpus.corpus_id,
        version=corpus.corpus_version,
        owner=corpus.owner,
        classification=corpus.classification,
        schema_version=corpus.schema_version,
        documents=tuple(documents),
    )


def ingest_summary(plan: IngestPlan, *, replaced_existing: bool) -> dict[str, Any]:
    kinds = sorted(
        {fact.kind for document in plan.documents for fact in document.facts}
    )
    return {
        "source": "store",
        "corpus_key": plan.corpus_key,
        "version": plan.version,
        "status": "approved",
        "owner": plan.owner,
        "classification": plan.classification,
        "document_count": len(plan.documents),
        "fact_count": plan.fact_count,
        "fact_kinds": kinds,
        "replaced_existing": replaced_existing,
    }


def corpus_from_store_rows(rows: list[dict[str, Any]]) -> Corpus:
    if not rows:
        raise ValueError("Approved corpus has no facts.")
    first = rows[0]
    facts: list[CorpusFact] = []
    for row in rows:
        kind = row.get("kind")
        if kind not in FACT_KINDS:
            raise ValueError(f"Unsupported fact kind {kind!r}.")
        terms = tuple(
            str(term).lower()
            for term in (row.get("search_terms") or [])
            if str(term).strip()
        )
        facts.append(
            CorpusFact(
                fact_id=str(row["fact_key"]),
                kind=kind,
                service_key=str(row.get("service_key") or ""),
                query_key=str(row["query_key"]),
                required_terms=terms,
                optional_terms=(),
                statement=str(row["statement"]),
                payload=dict(row.get("payload") or {}),
                source=SourceCitation(
                    corpus_id=str(first["corpus_key"]),
                    corpus_version=str(first["corpus_version"]),
                    document_id=str(row["document_key"]),
                    document_type=str(row["document_type"]),
                    document_version=str(row["document_version"]),
                    fact_id=str(row["fact_key"]),
                    classification=str(row.get("classification") or "internal"),
                    effective_from=str(row.get("effective_from") or ""),
                    effective_to=str(row.get("effective_to") or ""),
                ),
            )
        )
    return Corpus(
        corpus_id=str(first["corpus_key"]),
        corpus_version=str(first["corpus_version"]),
        schema_version=str(first.get("schema_version") or "store"),
        classification=str(first.get("corpus_classification") or first.get("classification") or "internal"),
        owner=str(first.get("owner") or "Commercial"),
        facts=tuple(facts),
    )
