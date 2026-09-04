"""AT-59 RAG: versioned corpus with citations and unknown answers."""

from __future__ import annotations

from services.borek_rag import RetrievalQuery, default_corpus, retrieve
from services.borek_rag.corpus import load_corpus
from services.borek_rag.ingest import plan_ingest


def test_corpus_is_versioned_and_contains_all_fact_kinds() -> None:
    corpus = default_corpus()
    kinds = {fact.kind for fact in corpus.facts}
    assert corpus.corpus_id == "borek-internal-dummy"
    assert corpus.corpus_version == "2026.09.03"
    assert corpus.owner == "Commercial"
    assert kinds == {"pricing", "staffing", "service", "reference"}
    assert all(fact.source.corpus_version == corpus.corpus_version for fact in corpus.facts)
    assert all(fact.source.document_version for fact in corpus.facts)


def test_pricing_question_returns_cited_rate_card_fact() -> None:
    result = retrieve(
        RetrievalQuery(
            text="What is the senior consultant day rate for Invoice 3-way Match?",
            kind="pricing",
        )
    )
    assert result.status == "answered"
    assert result.payload is not None
    assert result.payload["amount"] == "1250.00"
    assert result.payload["currency"] == "EUR"
    assert result.payload["indicative"] is True
    assert len(result.sources) == 1
    source = result.sources[0]
    assert source.document_id == "RC-DUMMY-2026-Q3"
    assert source.document_type == "rate_card"
    assert source.document_version == "2026.Q3.1"
    assert source.fact_id == "price.invoice-3way.senior-consultant.day-rate"
    assert source.corpus_version == "2026.09.03"


def test_staffing_question_returns_cited_team_fact() -> None:
    result = retrieve(
        RetrievalQuery(
            text="What staffing and FTE do we have for the invoice 3-way team?",
            kind="staffing",
        )
    )
    assert result.status == "answered"
    assert result.payload is not None
    assert result.payload["headcount"] == 4
    assert result.payload["total_fte"] == "2.6"
    source = result.sources[0]
    assert source.document_id == "STAFF-DUMMY-INV3WAY-v1"
    assert source.document_type == "staffing_profile"
    assert source.document_version == "1.0.0"
    assert source.fact_id == "staff.invoice-3way.core-team"


def test_service_and_reference_facts_are_cited() -> None:
    service = retrieve(
        RetrievalQuery(
            text="What is the Invoice 3-way Match service?",
            kind="service",
        )
    )
    assert service.status == "answered"
    assert service.payload is not None
    assert service.payload["service_key"] == "invoice_3way_match"
    assert service.sources[0].document_type == "service_definition"
    assert service.sources[0].fact_id.startswith("service.")

    reference = retrieve(
        RetrievalQuery(
            text="What reference delivery pattern do we use for invoice work?",
            kind="reference",
        )
    )
    assert reference.status == "answered"
    assert reference.payload is not None
    assert reference.payload["pattern"] == "structured_finance_operations"
    assert reference.sources[0].document_type == "reference"
    assert reference.sources[0].fact_id.startswith("reference.")


def test_query_key_lookup_is_traceable() -> None:
    result = retrieve(
        RetrievalQuery(
            text="",
            query_key="pricing:invoice_3way_match:senior_consultant:day_rate",
        )
    )
    assert result.status == "answered"
    assert result.sources[0].document_version == "2026.Q3.1"


def test_unsupported_pricing_returns_unknown_without_guessing() -> None:
    result = retrieve(
        RetrievalQuery(
            text="What is the senior consultant day rate for payroll automation?",
            kind="pricing",
        )
    )
    assert result.status == "unknown"
    assert result.statement is None
    assert result.payload is None
    assert result.sources == ()
    assert result.reason == "no_supported_fact"


def test_vague_question_does_not_invent_an_answer() -> None:
    result = retrieve(RetrievalQuery(text="What should we charge the client?"))
    assert result.status == "unknown"
    assert result.payload is None
    assert result.sources == ()


def test_kind_mismatch_does_not_reuse_another_fact() -> None:
    result = retrieve(
        RetrievalQuery(
            text="What staffing and FTE do we have for the invoice 3-way team?",
            kind="pricing",
        )
    )
    assert result.status == "unknown"
    assert result.payload is None


def test_ingest_plan_is_versioned_and_structured() -> None:
    from services.borek_rag.corpus import bundled_corpus_mapping

    plan = plan_ingest(bundled_corpus_mapping())
    assert plan.corpus_key == "borek-internal-dummy"
    assert plan.version == "2026.09.03"
    assert plan.owner == "Commercial"
    assert plan.fact_count == 4
    assert {document.document_type for document in plan.documents} == {
        "rate_card",
        "staffing_profile",
        "service_definition",
        "reference",
    }
    rate_card = next(
        document for document in plan.documents if document.document_type == "rate_card"
    )
    assert rate_card.source_uri.startswith("corpus://borek-internal-dummy/")
    assert rate_card.facts[0].payload["amount"] == "1250.00"


def test_unstructured_pricing_fact_is_not_returned() -> None:
    from dataclasses import replace

    from services.borek_rag.corpus import default_corpus

    corpus = default_corpus()
    loose = replace(
        corpus.facts[0],
        payload={"notes": "charge whatever feels right"},
    )
    broken = replace(corpus, facts=(loose, *corpus.facts[1:]))
    result = retrieve(
        RetrievalQuery(
            text="",
            query_key="pricing:invoice_3way_match:senior_consultant:day_rate",
        ),
        corpus=broken,
    )
    assert result.status == "unknown"
    assert result.payload is None
    assert result.reason == "unstructured_pricing_fact"


def test_load_corpus_rejects_empty_documents(tmp_path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(
        '{"corpus_id":"x","corpus_version":"1","schema_version":"s","classification":"internal","documents":[]}',
        encoding="utf-8",
    )
    try:
        load_corpus(path)
    except ValueError as exc:
        assert "at least one document" in str(exc)
    else:
        raise AssertionError("expected ValueError")
