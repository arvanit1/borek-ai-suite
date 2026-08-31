"""ES-5/ES-9: structured Claude output must not die on an undersized token cap."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm.claude.client import (
    CLAUDE_STRUCTURED_MAX_TOKENS,
    ClaudeClientError,
    structured_complete,
)
from llm.claude import client as client_module
from services.knowledge_model.extraction import extract_knowledge_model
from services.transcript.conversation_ids import allocate_transcript_identity
from services.transcript.speaker_turns import SpeakerTurn

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "contracts"
    / "fixtures"
    / "knowledge_model.minimal.json"
)


def _tool_response(stop_reason: str, payload: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        usage=None,
        content=[
            SimpleNamespace(
                type="tool_use",
                name="submit_knowledge_model",
                input=payload if payload is not None else {},
            )
        ],
    )


def test_undersized_cap_retries_at_model_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    calls: list[dict] = []

    def fake(kwargs, api_key):
        calls.append(kwargs)
        if len(calls) == 1:
            return _tool_response("max_tokens")
        return _tool_response("end_turn", {"facts": []})

    monkeypatch.setattr(client_module, "_stream_final_message", fake)

    result = structured_complete(
        "system",
        "user",
        {},
        tool_name="submit_knowledge_model",
        tool_description="Submit the KnowledgeModel JSON for this transcript.",
        max_tokens=12000,
    )

    assert result == {"facts": []}
    assert calls[0]["max_tokens"] == 12000
    assert calls[1]["max_tokens"] == CLAUDE_STRUCTURED_MAX_TOKENS
    assert "cut off at max_tokens" in calls[1]["messages"][0]["content"]


def test_ceiling_truncation_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    calls: list[dict] = []

    def fake(kwargs, api_key):
        calls.append(kwargs)
        if len(calls) == 1:
            return _tool_response("max_tokens")
        return _tool_response("end_turn", {"facts": [{"statement": "ERP"}]})

    monkeypatch.setattr(client_module, "_stream_final_message", fake)

    result = structured_complete(
        "system",
        "user",
        {},
        tool_name="submit_knowledge_model",
        tool_description="Submit the KnowledgeModel JSON for this transcript.",
        max_tokens=CLAUDE_STRUCTURED_MAX_TOKENS,
    )

    assert result["facts"][0]["statement"] == "ERP"
    assert [call["max_tokens"] for call in calls] == [
        CLAUDE_STRUCTURED_MAX_TOKENS,
        CLAUDE_STRUCTURED_MAX_TOKENS,
    ]


def test_still_truncated_after_retry_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def fake(kwargs, api_key):
        return _tool_response("max_tokens")

    monkeypatch.setattr(client_module, "_stream_final_message", fake)

    with pytest.raises(ClaudeClientError) as exc_info:
        structured_complete(
            "system",
            "user",
            {},
            tool_name="submit_knowledge_model",
            tool_description="Submit the KnowledgeModel JSON for this transcript.",
        )
    assert "truncated" in str(exc_info.value).lower()


def test_live_extraction_requests_model_output_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake(*args, **kwargs):
        captured["max_tokens"] = kwargs["max_tokens"]
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    monkeypatch.setattr(
        "services.knowledge_model.extraction.structured_complete",
        fake,
    )
    identity = allocate_transcript_identity("00000000-0000-4000-8000-000000000001")
    model = extract_knowledge_model(
        [SpeakerTurn(0, "Sandra", "We match invoices in the ERP.")],
        identity,
        redact=False,
        complete=None,
    )
    assert captured["max_tokens"] == CLAUDE_STRUCTURED_MAX_TOKENS
    assert model["named_systems"]
