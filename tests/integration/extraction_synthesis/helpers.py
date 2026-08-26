"""Shared helpers for ES-34 extraction + synthesis integration tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from services.framework.pipeline import generate_customer_framework
from services.framework.synthesis import PROMPT_VERSION as SYNTHESIS_PROMPT_VERSION
from services.knowledge_model.extraction import PROMPT_VERSION as EXTRACTION_PROMPT_VERSION
from services.knowledge_model.extraction import extract_knowledge_model
from services.knowledge_model.source_refs import KNOWLEDGE_BUCKETS
from services.transcript.conversation_ids import TranscriptIdentity, allocate_transcript_identity
from services.transcript.speaker_turns import split_speaker_turns

ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / "tests" / "eval" / "fixtures"

ClaudeComplete = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def load_manifest() -> dict[str, Any]:
    return json.loads((EVAL / "manifest.json").read_text(encoding="utf-8"))


def load_json(relative_path: str) -> dict[str, Any]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def align_km_fixture(km_fixture: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    """Rewrite fixture refs so extraction validates against the transcript identity."""
    aligned = json.loads(json.dumps(km_fixture))
    aligned["conversation_id"] = conversation_id
    for bucket in KNOWLEDGE_BUCKETS:
        for entry in aligned.get(bucket) or []:
            for ref in entry.get("source_refs") or []:
                ref["conversation_id"] = conversation_id
    return aligned


def align_draft_conversation_ids(draft: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    """Rewrite chapter source_refs so synthesis validates against the extracted KM."""
    aligned = json.loads(json.dumps(draft))
    for chapter in aligned.get("chapters") or []:
        for ref in chapter.get("source_refs") or []:
            ref["conversation_id"] = conversation_id
    return aligned


def draft_from_framework(framework: dict[str, Any], *, conversation_id: str = "C1") -> dict[str, Any]:
    """Build a synthesis draft payload from a golden FrameworkObject."""
    fallback_ref = {
        "conversation_id": conversation_id,
        "speaker_role": "Speaker",
        "excerpt_pointer": "turn:0",
    }
    chapters = []
    for chapter in framework["chapters"]:
        refs = list(chapter.get("source_refs") or []) or [fallback_ref]
        chapters.append(
            {
                "chapter_id": chapter["chapter_id"],
                "title": chapter["title"],
                "body": chapter["body"],
                "source_refs": refs,
            }
        )
    return {
        "title": framework["title"],
        "department": framework["department"],
        "cover": {
            "tagline": framework["cover"].get("tagline") or "Customer framework report.",
            "sources_line": framework["cover"].get("sources_line") or "Sources from conversations.",
            "how_produced": framework["cover"].get("how_produced") or "Generated from conversations.",
        },
        "kpis": [
            {
                "name": item.get("name") or "KPI",
                "baseline": str(item.get("baseline") or ""),
                "target": str(item.get("target") or ""),
                "measured_via": str(item.get("measured_via") or ""),
            }
            for item in framework.get("kpis") or []
        ],
        "systems": [
            {
                "name": item.get("name") or "System",
                "role": item.get("role") or "named",
                "direction": item.get("direction") or "internal",
                "access_path": item.get("access_path") or "as named",
                "data_classification": item.get("data_classification") or "as reported",
                "status": item.get("status") or "available",
            }
            for item in framework.get("systems") or []
        ],
        "rules": [
            {"name": item.get("name") or "Rule", "logic": item.get("logic") or item.get("name") or "named"}
            for item in framework.get("rules") or []
        ],
        "exceptions": [
            {
                "name": item.get("name") or "Exception",
                "frequency": item.get("frequency") or "named",
                "handling": item.get("handling") or "queued",
            }
            for item in framework.get("exceptions") or []
        ],
        "access_needs": [
            {
                "category": item.get("category") or "Access",
                "detail": item.get("detail") or "named",
                "status": item.get("status") or "named in conversation",
                "owner": item.get("owner") or "IT",
            }
            for item in framework.get("access_needs") or []
        ],
        "open_items": [
            {
                "description": item.get("description") or "Open item",
                "item_type": item.get("item_type")
                if item.get("item_type") in {"dependency", "assumption"}
                else "assumption",
                "owner": item.get("owner") or "Business",
                "consequence_if_different": item.get("consequence_if_different") or "Confirm before build.",
            }
            for item in framework.get("open_items") or []
        ],
        "chapters": chapters,
    }


def build_synthesis_draft(expected: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    return align_draft_conversation_ids(
        draft_from_framework(expected, conversation_id=conversation_id),
        conversation_id,
    )


def identity_from_knowledge_fixture(km_fixture: dict[str, Any]) -> TranscriptIdentity:
    """Mint ES-3 ids aligned with the checked-in KnowledgeModel fixture."""
    transcript_id = str(km_fixture.get("transcript_id") or "").strip()
    opportunity_seed = transcript_id or "00000000-0000-4000-8000-000000000001"
    return allocate_transcript_identity(
        opportunity_seed,
        transcript_id=transcript_id or None,
        conversation_id=str(km_fixture.get("conversation_id") or "C1"),
    )


def identity_for_live_case(case: dict[str, Any]) -> TranscriptIdentity:
    """Fresh ES-3 identity for a live Claude run (first conversation on the opportunity)."""
    km_fixture = load_json(case["knowledge_model"])
    transcript_id = str(km_fixture.get("transcript_id") or "").strip()
    opportunity_seed = transcript_id or "00000000-0000-4000-8000-000000000001"
    return allocate_transcript_identity(
        opportunity_seed,
        transcript_id=transcript_id or None,
        conversation_id="C1",
    )


@dataclass(frozen=True)
class PipelineRun:
    knowledge_model: dict[str, Any]
    framework: dict[str, Any]
    extraction_calls: int
    synthesis_calls: int


def run_es34_pipeline(case: dict[str, Any]) -> PipelineRun:
    """Run ES-5 extraction then ES-9 synthesis for one ES-33 fixture case (Claude mocked)."""
    transcript_path = ROOT / case["transcript"]
    turns = split_speaker_turns(transcript_path.name, transcript_path.read_bytes())
    km_fixture = load_json(case["knowledge_model"])
    expected = load_json(case["expected_framework"])
    overrides = load_json(case["engine_overrides"])
    identity = identity_from_knowledge_fixture(km_fixture)

    extraction_calls = 0

    def extraction_complete(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        nonlocal extraction_calls
        extraction_calls += 1
        assert EXTRACTION_PROMPT_VERSION in system
        assert identity.conversation_id in user
        return align_km_fixture(km_fixture, identity.conversation_id)

    synthesis_calls = 0
    synthesis_draft = build_synthesis_draft(expected, identity.conversation_id)

    def synthesis_complete(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        nonlocal synthesis_calls
        synthesis_calls += 1
        assert SYNTHESIS_PROMPT_VERSION in system
        assert "KNOWLEDGE ENTRIES" in user
        return json.loads(json.dumps(synthesis_draft))

    knowledge_model = extract_knowledge_model(
        turns,
        identity,
        redact=True,
        complete=extraction_complete,
    )
    framework = generate_customer_framework(
        [knowledge_model],
        opportunity_id=knowledge_model["opportunity_id"],
        title_hint=case["title_hint"],
        use_llm=True,
        complete=synthesis_complete,
        engine_overrides=overrides,
    )
    return PipelineRun(
        knowledge_model=knowledge_model,
        framework=framework,
        extraction_calls=extraction_calls,
        synthesis_calls=synthesis_calls,
    )


def run_es34_live_pipeline(case: dict[str, Any]) -> PipelineRun:
    """Run ES-5 + ES-9 against one ES-33 transcript with live Claude (requires ANTHROPIC_API_KEY)."""
    transcript_path = ROOT / case["transcript"]
    turns = split_speaker_turns(transcript_path.name, transcript_path.read_bytes())
    overrides = load_json(case["engine_overrides"])
    identity = identity_for_live_case(case)

    knowledge_model = extract_knowledge_model(turns, identity, redact=True)
    framework = generate_customer_framework(
        [knowledge_model],
        opportunity_id=knowledge_model["opportunity_id"],
        title_hint=case["title_hint"],
        use_llm=True,
        engine_overrides=overrides,
    )
    return PipelineRun(
        knowledge_model=knowledge_model,
        framework=framework,
        extraction_calls=1,
        synthesis_calls=1,
    )
