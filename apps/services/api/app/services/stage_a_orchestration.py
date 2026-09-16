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
from services.framework.synthesis import synthesize_customer_chapter
from services.framework.review_insights import attach_review_insights, opportunity_pii_redaction_enabled
from app.services.knowledge_access import resolve_active_corpus
from services.framework.client_pack import (
    apply_client_pack_to_framework,
    normalize_client_pack,
)
from services.framework.company_facts import (
    apply_company_facts_to_framework,
    ground_company_facts,
    query_text_from_opportunity,
)
from services.knowledge_model.extraction import PROMPT_VERSION as EXTRACTION_PROMPT_VERSION
from services.knowledge_model.extraction import extract_knowledge_model
from services.transcript.conversation_ids import TranscriptIdentity
from services.transcript.speaker_turns import SpeakerTurn

ExtractFn = Callable[..., dict[str, Any]]
GenerateFn = Callable[..., dict[str, Any]]
ChapterFn = Callable[..., dict[str, Any]]


def generate_framework_from_transcripts(
    store: Any,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    execution_mode: str | None = None,
    extract_fn: ExtractFn = extract_knowledge_model,
    generate_fn: GenerateFn = generate_customer_framework,
    job_id: UUID | None = None,
    transcript_ids: list[str] | None = None,
    stage_callback: Callable[[str], None] | None = None,
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
    if transcript_ids is not None:
        by_id = {str(source["id"]): source for source in sources}
        if any(transcript_id not in by_id for transcript_id in transcript_ids):
            raise bad_request("TRANSCRIPT_SET_CHANGED", "A transcript pinned to this generation job is no longer available")
        sources = [by_id[transcript_id] for transcript_id in transcript_ids]
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    client_pack = normalize_client_pack(opportunity.get("additional_client_information"))
    company_facts = ground_company_facts(
        query_text_from_opportunity(opportunity),
        corpus=_corpus_for_store(store),
    )
    if mode != "live":
        if stage_callback is not None:
            stage_callback("knowledge")
            stage_callback("synthesis")
        payload = load_framework_stub_template(opportunity_id)
        if sources:
            payload["generated_from"] = [str(source["id"]) for source in sources]
        apply_client_pack_to_framework(payload, client_pack)
        apply_company_facts_to_framework(payload, company_facts)
        result = attach_review_insights(
            payload,
            pii_redaction_enabled=opportunity_pii_redaction_enabled(opportunity),
        )
        if stage_callback is not None:
            stage_callback("validation")
        return result
    if not sources:
        raise bad_request(
            "TRANSCRIPT_REQUIRED",
            "Upload at least one valid transcript before generating a framework",
        )

    redact = opportunity_pii_redaction_enabled(opportunity)
    checkpoints: dict[str, dict[str, Any]] = {}
    if job_id is not None and hasattr(store, "list_job_knowledge_models"):
        checkpoints = {
            str(row["transcript_id"]): row
            for row in store.list_job_knowledge_models(
                job_id=job_id,
                opportunity_id=opportunity_id,
                user_id=user_id,
            )
        }
    if any(str(source["id"]) not in checkpoints for source in sources) and stage_callback is not None:
        stage_callback("knowledge")
    knowledge_models: list[dict[str, Any]] = []
    for source in sources:
        checkpoint = checkpoints.get(str(source["id"]))
        if checkpoint is not None:
            if (
                str(checkpoint.get("conversation_id") or "") != str(source["conversation_id"])
                or str(checkpoint.get("schema_version") or "") != "1.0"
                or str(checkpoint.get("prompt_version") or "") != EXTRACTION_PROMPT_VERSION
            ):
                raise bad_request("KNOWLEDGE_CHECKPOINT_INVALID", "Stored extraction checkpoint does not match this generation job")
            knowledge_models.append(copy.deepcopy(checkpoint["knowledge_model_json"]))
            continue
        turns = _speaker_turns(source)
        identity = TranscriptIdentity(
            opportunity_id=str(opportunity_id),
            transcript_id=str(source["id"]),
            conversation_id=str(source["conversation_id"]),
        )
        model = _call_with_optional_kwargs(
            extract_fn,
            turns,
            identity,
            redact=redact,
            client_pack=client_pack,
        )
        knowledge_models.append(model)
        if job_id is not None and hasattr(store, "upsert_job_knowledge_model"):
            store.upsert_job_knowledge_model(
                job_id=job_id,
                transcript_id=source["id"],
                opportunity_id=opportunity_id,
                user_id=user_id,
                conversation_id=str(source["conversation_id"]),
                knowledge_model_json=model,
                schema_version=str(model.get("schema_version") or "1.0"),
                prompt_version=EXTRACTION_PROMPT_VERSION,
            )
        store.update_transcript_processing_status(
            opportunity_id=opportunity_id,
            transcript_id=source["id"],
            user_id=user_id,
            processing_status="processed",
        )

    if stage_callback is not None:
        stage_callback("synthesis")
    framework = _call_with_optional_kwargs(
        generate_fn,
        knowledge_models,
        opportunity_id=str(opportunity_id),
        title_hint=str(opportunity.get("opportunity_name") or "") or None,
        lang=str(opportunity.get("language") or "en"),
        use_llm=True,
        client_pack=client_pack,
        company_facts=company_facts,
        stage_callback=stage_callback,
    )
    if stage_callback is not None:
        stage_callback("validation")

    payload = copy.deepcopy(framework)
    payload["opportunity_id"] = str(opportunity_id)
    payload["status"] = "draft"
    payload["generated_from"] = [str(source["id"]) for source in sources]
    apply_client_pack_to_framework(payload, client_pack)
    apply_company_facts_to_framework(payload, company_facts)
    result = attach_review_insights(payload, pii_redaction_enabled=redact)
    return result


def regenerate_framework_chapter_from_transcripts(
    store: Any,
    *,
    opportunity_id: UUID,
    user_id: UUID,
    framework: dict[str, Any],
    chapter_id: str,
    execution_mode: str | None = None,
    extract_fn: ExtractFn = extract_knowledge_model,
    chapter_fn: ChapterFn = synthesize_customer_chapter,
    stage_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Produce one replacement chapter from the persisted transcript evidence."""
    matches = [
        chapter
        for chapter in framework.get("chapters") or []
        if str(chapter.get("chapter_id")) == str(chapter_id)
    ]
    if len(matches) != 1:
        raise bad_request("INVALID_CHAPTER_ID", f"Chapter {chapter_id} was not found")
    current = matches[0]
    mode = execution_mode or settings.AI_EXECUTION_MODE
    if mode != "live":
        replacement = copy.deepcopy(current)
        body = replacement.get("body")
        marker = {"block": "callout", "text": f"Fixture regeneration for chapter {chapter_id}."}
        if isinstance(body, list):
            replacement["body"] = [*body, marker]
        else:
            replacement["body"] = f"{str(body or '').strip()} Fixture regeneration for chapter {chapter_id}.".strip()
        return replacement

    sources = store.list_transcript_sources(opportunity_id=opportunity_id, user_id=user_id)
    if not sources:
        raise bad_request("TRANSCRIPT_REQUIRED", "Upload at least one valid transcript before regenerating a chapter")
    opportunity = store.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
    client_pack = normalize_client_pack(opportunity.get("additional_client_information"))
    redact = opportunity_pii_redaction_enabled(opportunity)
    if stage_callback is not None:
        stage_callback("knowledge")
    knowledge_models: list[dict[str, Any]] = []
    for source in sources:
        identity = TranscriptIdentity(
            opportunity_id=str(opportunity_id),
            transcript_id=str(source["id"]),
            conversation_id=str(source["conversation_id"]),
        )
        knowledge_models.append(
            _call_with_optional_kwargs(
                extract_fn,
                _speaker_turns(source),
                identity,
                redact=redact,
                client_pack=client_pack,
            )
        )
    if stage_callback is not None:
        stage_callback("synthesis")
    llm_framework = _redact_framework_for_llm(framework, enabled=redact)
    return _call_with_optional_kwargs(
        chapter_fn,
        framework=llm_framework,
        knowledge_models=knowledge_models,
        chapter_id=chapter_id,
        opportunity_id=str(opportunity_id),
    )


def _redact_framework_for_llm(value: Any, *, enabled: bool) -> Any:
    if not enabled:
        return copy.deepcopy(value)
    if isinstance(value, dict):
        return {
            _redact_framework_for_llm(key, enabled=True) if isinstance(key, str) else key: _redact_framework_for_llm(
                item,
                enabled=True,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_framework_for_llm(item, enabled=True) for item in value]
    if isinstance(value, str):
        from services.transcript.pii_redaction import redact_turns_for_llm

        redacted = redact_turns_for_llm(
            [SpeakerTurn(turn_index=0, speaker="unknown", text=value)],
            enabled=True,
        )
        return redacted[0].text
    return copy.deepcopy(value)


def _corpus_for_store(store: Any):
    lister = getattr(store, "list_approved_knowledge_facts", None)
    if not callable(lister):
        return None
    return resolve_active_corpus(store)


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
