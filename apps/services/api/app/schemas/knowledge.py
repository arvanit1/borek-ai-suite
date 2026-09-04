"""Authenticated Borek knowledge retrieval contracts (AT-59)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FactKind = Literal["service", "pricing", "staffing", "reference"]


class KnowledgeRetrievalRequest(BaseModel):
    text: str = Field(default="", max_length=2000)
    kind: FactKind | None = None
    query_key: str | None = Field(default=None, max_length=200)
    service_key: str | None = Field(default=None, max_length=200)


class KnowledgeSourceResponse(BaseModel):
    corpus_id: str
    corpus_version: str
    document_id: str
    document_type: str
    document_version: str
    fact_id: str
    classification: str
    effective_from: str
    effective_to: str


class KnowledgeRetrievalResponse(BaseModel):
    status: Literal["answered", "unknown"]
    statement: str | None = None
    payload: dict[str, Any] | None = None
    sources: list[KnowledgeSourceResponse] = Field(default_factory=list)
    reason: str


class KnowledgeIngestRequest(BaseModel):
    corpus: dict[str, Any] | None = None


class KnowledgeCorpusResponse(BaseModel):
    source: Literal["store", "bundled_dummy"]
    corpus_key: str
    version: str
    status: Literal["draft", "approved", "retired"]
    owner: str
    classification: str
    document_count: int
    fact_count: int
    fact_kinds: list[str] = Field(default_factory=list)
    replaced_existing: bool | None = None
