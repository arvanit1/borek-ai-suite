"""Stage 3: injected provider timeout, malformed output, and schema retry."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.services.stage_a_orchestration import generate_framework_from_transcripts
from llm.claude.client import ClaudeClientError
from services.framework.synthesis import FrameworkSynthesisError, synthesize_customer_draft
from services.knowledge_model.extraction import KnowledgeExtractionError, extract_knowledge_model
from services.transcript.conversation_ids import allocate_transcript_identity
from services.transcript.speaker_turns import SpeakerTurn
from tests.unit.api.test_stage_a_orchestration import (
    OPPORTUNITY_ID,
    TRANSCRIPT_ID,
    USER_ID,
    SourceStore,
    _source,
)
from tests.unit.framework.test_synthesis import _base_framework, _draft_from_framework

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "contracts"
    / "fixtures"
    / "knowledge_model.minimal.json"
)


def _turns() -> list[SpeakerTurn]:
    return [SpeakerTurn(0, "Sandra", "We match invoices in the ERP.")]


def _identity():
    return allocate_transcript_identity("00000000-0000-4000-8000-000000000001")


def test_extraction_timeout_is_retryable_and_stays_on_knowledge_stage() -> None:
    def timeout(*_args, **_kwargs):
        raise TimeoutError("claude timed out")

    with pytest.raises(KnowledgeExtractionError) as raised:
        extract_knowledge_model(_turns(), _identity(), complete=timeout)
    assert raised.value.code == "PROVIDER_TIMEOUT"
    assert raised.value.retryable is True

    stages: list[str] = []
    with pytest.raises(KnowledgeExtractionError):
        generate_framework_from_transcripts(
            SourceStore(sources=[_source()]),
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
            execution_mode="live",
            extract_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                KnowledgeExtractionError(
                    "Claude timed out before the KnowledgeModel was complete.",
                    code="PROVIDER_TIMEOUT",
                    retryable=True,
                )
            ),
            generate_fn=lambda *_args, **_kwargs: pytest.fail("synthesis must not run"),
            stage_callback=stages.append,
        )
    assert stages == ["knowledge"]


def test_malformed_extraction_payload_is_not_retryable() -> None:
    def malformed(*_args, **_kwargs):
        return ["not", "an", "object"]

    with pytest.raises(KnowledgeExtractionError, match="JSON object") as raised:
        extract_knowledge_model(_turns(), _identity(), complete=malformed)
    assert raised.value.retryable is False


def test_malformed_synthesis_payload_is_not_retryable() -> None:
    def malformed(*_args, **_kwargs):
        return "not-json"

    with pytest.raises(FrameworkSynthesisError, match="JSON object") as raised:
        synthesize_customer_draft(skeleton={}, engine_outputs={}, complete=malformed)
    assert raised.value.retryable is False


def test_synthesis_timeout_is_retryable_and_stays_on_synthesis_stage() -> None:
    def timeout(*_args, **_kwargs):
        raise TimeoutError("claude timed out")

    with pytest.raises(FrameworkSynthesisError) as raised:
        synthesize_customer_draft(skeleton={}, engine_outputs={}, complete=timeout)
    assert raised.value.code == "PROVIDER_TIMEOUT"
    assert raised.value.retryable is True

    stages: list[str] = []
    with pytest.raises(FrameworkSynthesisError):
        generate_framework_from_transcripts(
            SourceStore(sources=[_source()]),
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
            execution_mode="live",
            extract_fn=lambda *_args, **_kwargs: {"schema_version": "1.0", "conversation_id": "C1", "facts": []},
            generate_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                FrameworkSynthesisError(
                    "Claude timed out before the customer report was complete.",
                    code="PROVIDER_TIMEOUT",
                    retryable=True,
                )
            ),
            stage_callback=stages.append,
        )
    assert stages == ["knowledge", "synthesis"]


def test_claude_timeout_error_keeps_provider_code() -> None:
    def boom(*_args, **_kwargs):
        raise ClaudeClientError("timed out waiting", code="PROVIDER_TIMEOUT", retryable=True)

    with pytest.raises(KnowledgeExtractionError) as raised:
        extract_knowledge_model(_turns(), _identity(), complete=boom)
    assert raised.value.code == "PROVIDER_TIMEOUT"
    assert raised.value.retryable is True


def test_short_then_valid_synthesis_retries_once() -> None:
    valid = _draft_from_framework(_base_framework())
    short = dict(valid)
    short["chapters"] = valid["chapters"][:13]
    responses = [short, valid]
    users: list[str] = []

    def complete(system: str, user: str, schema: dict) -> dict:
        users.append(user)
        return responses[len(users) - 1]

    result = synthesize_customer_draft(skeleton={}, engine_outputs={}, complete=complete)
    assert len(users) == 2
    assert len(result["chapters"]) == 14


def test_extraction_checkpoint_survives_malformed_synthesis_retry() -> None:
    store = SourceStore(sources=[_source()])
    job_id = uuid.uuid4()
    extraction_calls = 0

    def extract(*_args, **_kwargs) -> dict:
        nonlocal extraction_calls
        extraction_calls += 1
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8")) | {
            "schema_version": "1.0",
            "conversation_id": "C1",
        }

    with pytest.raises(FrameworkSynthesisError, match="JSON object"):
        generate_framework_from_transcripts(
            store,
            opportunity_id=OPPORTUNITY_ID,
            user_id=USER_ID,
            execution_mode="live",
            extract_fn=extract,
            generate_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                FrameworkSynthesisError("Claude did not return a JSON object for the customer report.")
            ),
            job_id=job_id,
            transcript_ids=[str(TRANSCRIPT_ID)],
        )

    result = generate_framework_from_transcripts(
        store,
        opportunity_id=OPPORTUNITY_ID,
        user_id=USER_ID,
        execution_mode="live",
        extract_fn=extract,
        generate_fn=lambda *_args, **_kwargs: {"schema_version": "1.0", "status": "draft", "chapters": []},
        job_id=job_id,
        transcript_ids=[str(TRANSCRIPT_ID)],
    )
    assert extraction_calls == 1
    assert result["generated_from"] == [str(TRANSCRIPT_ID)]
