"""Versioned Borek corpus types for the Phase 2 RAG spike (AT-59 shape)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

FactKind = Literal["service", "pricing", "staffing", "reference"]
AnswerStatus = Literal["answered", "unknown"]


@dataclass(frozen=True)
class SourceCitation:
    corpus_id: str
    corpus_version: str
    document_id: str
    document_type: str
    document_version: str
    fact_id: str
    classification: str
    effective_from: str
    effective_to: str


@dataclass(frozen=True)
class CorpusFact:
    fact_id: str
    kind: FactKind
    service_key: str
    query_key: str
    required_terms: tuple[str, ...]
    optional_terms: tuple[str, ...]
    statement: str
    payload: dict[str, Any]
    source: SourceCitation


@dataclass(frozen=True)
class Corpus:
    corpus_id: str
    corpus_version: str
    schema_version: str
    classification: str
    owner: str
    facts: tuple[CorpusFact, ...]


@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    kind: FactKind | None = None
    query_key: str | None = None
    service_key: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    status: AnswerStatus
    statement: str | None
    payload: dict[str, Any] | None
    sources: tuple[SourceCitation, ...]
    reason: str
