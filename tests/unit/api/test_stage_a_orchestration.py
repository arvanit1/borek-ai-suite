"""AT-40/41 join tests: platform persistence invokes ES entrypoints unchanged."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import HTTPException

from app.services.stage_a_orchestration import generate_framework_from_transcripts

OPPORTUNITY_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TRANSCRIPT_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class SourceStore:
    def __init__(self, *, sources: list[dict[str, Any]]) -> None:
        self.sources = sources
        self.status_updates: list[tuple[uuid.UUID, str]] = []
        self.checkpoints: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Any]] = {}

    def list_transcript_sources(self, **_: Any) -> list[dict[str, Any]]:
        return self.sources

    def get_opportunity(self, **_: Any) -> dict[str, Any]:
        return {
            "opportunity_name": "Invoice Automation",
            "language": "en",
        }

    def update_transcript_processing_status(
        self,
        *,
        transcript_id: uuid.UUID,
        processing_status: str,
        **_: Any,
    ) -> None:
        self.status_updates.append((transcript_id, processing_status))

    def list_job_knowledge_models(self, *, job_id: uuid.UUID, **_: Any) -> list[dict[str, Any]]:
        return [row for (stored_job_id, _), row in self.checkpoints.items() if stored_job_id == job_id]

    def upsert_job_knowledge_model(
        self,
        *,
        job_id: uuid.UUID,
        transcript_id: uuid.UUID,
        opportunity_id: uuid.UUID,
        conversation_id: str,
        knowledge_model_json: dict[str, Any],
        schema_version: str,
        prompt_version: str,
        **_: Any,
    ) -> dict[str, Any]:
        row = {
            "generation_job_id": job_id,
            "transcript_id": transcript_id,
            "opportunity_id": opportunity_id,
            "conversation_id": conversation_id,
            "knowledge_model_json": knowledge_model_json,
            "schema_version": schema_version,
            "prompt_version": prompt_version,
        }
        self.checkpoints[(job_id, transcript_id)] = row
        return row


def _source() -> dict[str, Any]:
    return {
        "id": TRANSCRIPT_ID,
        "file_name": "meeting.txt",
        "conversation_id": "C1",
        "sections": [
            {
                "section_index": 0,
                "speaker_role": "Alex",
                "content": "We process invoices in SAP.",
                "metadata": {"conversation_id": "C1"},
            }
        ],
    }


def test_live_mode_invokes_es_extraction_then_framework_pipeline() -> None:
    calls: list[str] = []
    store = SourceStore(sources=[_source()])

    def extract(turns: list[Any], identity: Any, *, redact: bool) -> dict[str, Any]:
        calls.append("extract")
        assert [(turn.turn_index, turn.speaker, turn.text) for turn in turns] == [
            (0, "Alex", "We process invoices in SAP.")
        ]
        assert identity.transcript_id == str(TRANSCRIPT_ID)
        assert identity.conversation_id == "C1"
        assert redact is True
        return {"conversation_id": "C1", "facts": []}

    def generate(
        models: list[dict[str, Any]],
        *,
        opportunity_id: str,
        title_hint: str,
        lang: str,
        use_llm: bool,
    ) -> dict[str, Any]:
        calls.append("generate")
        assert models == [{"conversation_id": "C1", "facts": []}]
        assert opportunity_id == str(OPPORTUNITY_ID)
        assert title_hint == "Invoice Automation"
        assert lang == "en"
        assert use_llm is True
        return {"schema_version": "1.0", "status": "draft", "chapters": []}

    result = generate_framework_from_transcripts(
        store,
        opportunity_id=OPPORTUNITY_ID,
        user_id=USER_ID,
        execution_mode="live",
        extract_fn=extract,
        generate_fn=generate,
    )

    assert calls == ["extract", "generate"]
    assert store.status_updates == [(TRANSCRIPT_ID, "processed")]
    assert result["generated_from"] == [str(TRANSCRIPT_ID)]
    assert result["opportunity_id"] == str(OPPORTUNITY_ID)


def test_live_mode_requires_a_persisted_transcript() -> None:
    with pytest.raises(HTTPException) as exc_info:
        generate_framework_from_transcripts(
            SourceStore(sources=[]),
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
            execution_mode="live",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "TRANSCRIPT_REQUIRED"


def test_synthesis_retry_reuses_job_scoped_knowledge_checkpoint() -> None:
    store = SourceStore(sources=[_source()])
    job_id = uuid.uuid4()
    extraction_calls = 0
    stage_runs: list[list[str]] = []

    def extract(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal extraction_calls
        extraction_calls += 1
        return {"schema_version": "1.0", "conversation_id": "C1", "facts": []}

    def fail_synthesis(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("synthesis unavailable")

    first_stages: list[str] = []
    with pytest.raises(RuntimeError, match="synthesis unavailable"):
        generate_framework_from_transcripts(
            store,
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
            execution_mode="live",
            extract_fn=extract,
            generate_fn=fail_synthesis,
            job_id=job_id,
            transcript_ids=[str(TRANSCRIPT_ID)],
            stage_callback=first_stages.append,
        )
    stage_runs.append(first_stages)

    second_stages: list[str] = []
    result = generate_framework_from_transcripts(
        store,
        opportunity_id=OPPORTUNITY_ID,
        user_id=USER_ID,
        execution_mode="live",
        extract_fn=extract,
        generate_fn=lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "status": "draft",
            "chapters": [],
        },
        job_id=job_id,
        transcript_ids=[str(TRANSCRIPT_ID)],
        stage_callback=second_stages.append,
    )
    stage_runs.append(second_stages)

    assert extraction_calls == 1
    assert stage_runs[0] == ["knowledge", "synthesis"]
    assert stage_runs[1] == ["synthesis", "validation"]
    assert result["generated_from"] == [str(TRANSCRIPT_ID)]


def test_extraction_failure_never_advances_to_synthesis() -> None:
    stages: list[str] = []

    with pytest.raises(RuntimeError, match="extraction unavailable"):
        generate_framework_from_transcripts(
            SourceStore(sources=[_source()]),
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
            execution_mode="live",
            extract_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("extraction unavailable")),
            generate_fn=lambda *_args, **_kwargs: pytest.fail("synthesis must not run"),
            stage_callback=stages.append,
        )

    assert stages == ["knowledge"]
