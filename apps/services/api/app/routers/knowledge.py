"""Authenticated retrieval and ingest of versioned Borek company facts (AT-59)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.config import settings
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.knowledge import (
    KnowledgeCorpusResponse,
    KnowledgeIngestRequest,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
    KnowledgeSourceResponse,
)
from app.services.api_errors import bad_request, forbidden
from app.services.knowledge_access import describe_active_corpus, resolve_active_corpus
from services.borek_rag import RetrievalQuery, retrieve
from services.borek_rag.corpus import bundled_corpus_mapping

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/retrieve", response_model=KnowledgeRetrievalResponse)
def retrieve_borek_knowledge(
    body: KnowledgeRetrievalRequest,
    _user: AuthUserDep,
    store: DataStoreDep,
) -> KnowledgeRetrievalResponse:
    """Retrieve only a uniquely supported, source-versioned company fact."""
    result = retrieve(
        RetrievalQuery(
            text=body.text,
            kind=body.kind,
            query_key=body.query_key,
            service_key=body.service_key,
        ),
        corpus=resolve_active_corpus(store),
    )
    return KnowledgeRetrievalResponse(
        status=result.status,
        statement=result.statement,
        payload=result.payload,
        sources=[
            KnowledgeSourceResponse.model_validate(asdict(source))
            for source in result.sources
        ],
        reason=result.reason,
    )


@router.get("/corpus", response_model=KnowledgeCorpusResponse)
def get_active_knowledge_corpus(
    _user: AuthUserDep,
    store: DataStoreDep,
) -> KnowledgeCorpusResponse:
    return KnowledgeCorpusResponse.model_validate(describe_active_corpus(store))


@router.post("/ingest", response_model=KnowledgeCorpusResponse)
def ingest_borek_knowledge(
    _user: AuthUserDep,
    store: DataStoreDep,
    body: KnowledgeIngestRequest | None = None,
) -> KnowledgeCorpusResponse:
    """Load a versioned corpus into the approved store. Memory/dev only via API."""
    if settings.API_DATA_BACKEND != "memory":
        raise forbidden(
            "KNOWLEDGE_INGEST_FORBIDDEN",
            "Corpus ingest through the API is limited to the memory backend; "
            "use the service-role ingest script against Supabase",
        )
    raw = body.corpus if body is not None and body.corpus is not None else bundled_corpus_mapping()
    try:
        return KnowledgeCorpusResponse.model_validate(store.ingest_approved_corpus(raw))
    except ValueError as exc:
        raise bad_request("INVALID_KNOWLEDGE_CORPUS", str(exc)) from exc
