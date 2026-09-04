"""Adapters that join the AT platform store to Endrit's Stage A engine.

This module owns orchestration only. Transcript parsing, extraction, framework
generation, and their validation remain implemented in ``apps/api/services``.
"""

from __future__ import annotations

import copy
import inspect
from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.config import settings
from app.services.api_errors import bad_request
from app.services.framework_stub_template import load_framework_stub_template
from services.framework.pipeline import generate_customer_framework
from services.framework.review_insights import attach_review_insights, opportunity_pii_redaction_enabled
from services.framework.client_pack import (
    apply_client_pack_to_framework,
    normalize_client_pack,
)
from services.knowledge_model.extraction import extract_knowledge_model
from services.transcript.conversation_ids import TranscriptIdentity
from services.transcript.speaker_turns import SpeakerTurn

ExtractFn = Callable[..., dict[str, Any]]
GenerateFn = Callable[..., dict[str, Any]]


def generate_framework_from_transcripts(
    store: Any,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    execution_mode: str | None = None,
    extract_fn: ExtractFn = extract_knowledge_model,
    generate_fn: GenerateFn = generate_customer_framework,
) -> dict[str, Any]:
    """Create a FrameworkObject from persisted transcript sections.

    ``fixture`` mode preserves deterministic local/test behavior. ``live`` mode
    invokes the existing ES-5 and ES-9 entrypoints without changing them.
    """
    mode = execution_mode or settings.AI_EXECUTION_MODE
    sources = store.list_transcript_sources(
        opportunity_id=opportunity_id,
        user_id=user_id,
    )
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    client_pack = normalize_client_pack(opportunity.get("additional_client_information"))
    if mode != "live":
        payload = load_framework_stub_template(opportunity_id)
        if sources:
            payload["generated_from"] = [str(source["id"]) for source in sources]
        apply_client_pack_to_framework(payload, client_pack)
        return attach_review_insights(
            payload,
            pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
        )
    if not sources:
        raise bad_request(
            "TRANSCRIPT_REQUIRED",
            "Upload at least one valid transcript before generating a framework",
        )

    redact = opportunity_pii_redaction_enabled(opportunity)
    knowledge_models: list[dict[str, Any]] = []
    for source in sources:
        turns = _speaker_turns(source)
        identity = TranscriptIdentity(
            opportunity_id=str(opportunity_id),
            transcript_id=str(source["id"]),
            conversation_id=str(source["conversation_id"]),
        )
        try:
            knowledge_models.append(
                _call_with_optional_kwargs(
                    extract_fn,
                    turns,
                    identity,
                    redact=redact,
                    client_pack=client_pack,
                )
            )
        except Exception as exc:
            user_message = getattr(exc, "user_message", str(exc))
            raise bad_request("KNOWLEDGE_EXTRACTION_FAILED", user_message) from exc
        store.update_transcript_processing_status(
            opportunity_id=opportunity_id,
            transcript_id=source["id"],
            user_id=user_id,
            processing_status="processed",
        )

    try:
        framework = _call_with_optional_kwargs(
            generate_fn,
            knowledge_models,
            opportunity_id=str(opportunity_id),
            title_hint=str(opportunity.get("opportunity_name") or "") or None,
            lang=str(opportunity.get("language") or "en"),
            use_llm=True,
            client_pack=client_pack,
        )
    except Exception as exc:
        user_message = getattr(exc, "user_message", str(exc))
        raise bad_request("FRAMEWORK_GENERATION_FAILED", user_message) from exc

    payload = copy.deepcopy(framework)
    payload["opportunity_id"] = str(opportunity_id)
    payload["status"] = "draft"
    payload["generated_from"] = [str(source["id"]) for source in sources]
    apply_client_pack_to_framework(payload, client_pack)
    return attach_review_insights(payload, pii_redaction_enabled=redact)


def _call_with_optional_kwargs(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(*args, **{key: value for key, value in kwargs.items() if key != "client_pack"})
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return fn(*args, **kwargs)
    accepted = {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }
    return fn(*args, **accepted)


def _speaker_turns(source: dict[str, Any]) -> list[SpeakerTurn]:
    turns = [
        SpeakerTurn(
            turn_index=int(section["section_index"]),
            speaker=str(section.get("speaker_role") or "unknown"),
            text=str(section["content"]),
        )
        for section in source.get("sections") or []
    ]
    if not turns:
        raise bad_request(
            "TRANSCRIPT_CONTENT_MISSING",
            f"Transcript {source['id']} has no persisted speaker turns",
        )
    return turns
