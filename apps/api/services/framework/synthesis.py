"""ES-9 — one Claude Sonnet call: KnowledgeModel → 14-chapter customer report."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import jsonschema

from llm.claude.client import (
    CLAUDE_STRUCTURED_MAX_TOKENS,
    ClaudeClientError,
    sonnet_model,
    structured_complete,
)
from packages.contracts.validators import chapter_specs_from_registry
from services.framework.chapter_builder import overlay_llm_chapters
from services.framework.config_loader import repo_root, tone_voice
from services.framework.client_pack import format_client_pack_for_prompt
from services.knowledge_model.source_refs import (
    collect_customer_report_source_ref_violations,
    parse_turn_index,
)
from services.observability.llm_logger import STAGE_SYNTHESIS, run_logged_llm_call
from services.validation.schema_retry import SourceRefRetryError, require_valid_source_refs

PROMPT_VERSION = "framework-synthesis:v1"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "llm" / "claude" / "prompts" / "synthesis_v1.txt"
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "llm" / "claude" / "prompts" / "customer_report.schema.json"

ClaudeComplete = Callable[[str, str, dict[str, Any]], dict[str, Any]]


class FrameworkSynthesisError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def load_customer_report_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def synthesize_customer_draft(
    *,
    skeleton: dict[str, Any],
    engine_outputs: dict[str, Any],
    complete: ClaudeComplete | None = None,
    opportunity_id: str | None = None,
    client_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One structured Claude call. The draft must contain all 14 registry chapters."""
    system = _system_prompt()
    base_user = _user_prompt(skeleton, engine_outputs, client_pack=client_pack)
    schema = load_customer_report_schema()
    runner = complete or _anthropic_complete
    allowed_cids, allowed_turns = _allowed_citation_scope(skeleton)
    opp_id = opportunity_id or str(skeleton.get("opportunity_id") or "")
    attempt_counter = 0

    def call(feedback: str | None) -> dict[str, Any]:
        nonlocal attempt_counter
        attempt_counter += 1
        user = base_user
        if feedback:
            user = f"{base_user}\n\nRETRY — fix source_refs on every chapter:\n{feedback}"
        usage_holder: list[Any] = []

        def invoke() -> dict[str, Any]:
            try:
                raw = structured_complete(
                    system,
                    user,
                    schema,
                    tool_name="submit_customer_report",
                    tool_description="Submit the 14-chapter customer report draft.",
                    max_tokens=CLAUDE_STRUCTURED_MAX_TOKENS,
                    temperature=0,
                    usage_out=usage_holder,
                )
            except ClaudeClientError as exc:
                raise FrameworkSynthesisError(exc.user_message) from exc
            if not isinstance(raw, dict):
                raise FrameworkSynthesisError("Claude did not return a JSON object for the customer report.")
            return _coerce_draft(raw)

        if complete is None:
            return run_logged_llm_call(
                stage=STAGE_SYNTHESIS,
                prompt_version=PROMPT_VERSION,
                model=sonnet_model(),
                attempt=attempt_counter,
                opportunity_id=opp_id or None,
                usage_out=usage_holder,
                invoke=invoke,
            )
        raw = runner(system, user, schema)
        if not isinstance(raw, dict):
            raise FrameworkSynthesisError("Claude did not return a JSON object for the customer report.")
        return _coerce_draft(raw)

    def collect(draft: dict[str, Any]) -> list:
        return collect_customer_report_source_ref_violations(
            draft,
            allowed_conversation_ids=sorted(allowed_cids) if allowed_cids else None,
            allowed_turn_indices=sorted(allowed_turns) if allowed_turns else None,
        )

    try:
        draft, _attempts = require_valid_source_refs(call=call, collect_violations=collect)
    except SourceRefRetryError as exc:
        raise FrameworkSynthesisError(exc.user_message) from exc
    return _finalize_customer_draft(draft, schema)


def _finalize_customer_draft(draft: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    try:
        jsonschema.validate(instance=draft, schema=schema)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "(root)"
        raise FrameworkSynthesisError(
            f"Customer report draft failed schema validation at {path}. All 14 chapters are required."
        ) from exc
    _assert_registry_chapters(draft)
    return draft


def _allowed_citation_scope(skeleton: dict[str, Any]) -> tuple[set[str], set[int]]:
    conversation_ids = {
        str(item).strip()
        for item in (skeleton.get("conversation_ids") or [])
        if item and str(item).strip()
    }
    turn_indices: set[int] = set()
    for entry in skeleton.get("source_entries") or []:
        if not isinstance(entry, dict):
            continue
        for ref in entry.get("source_refs") or []:
            if not isinstance(ref, dict):
                continue
            cid = str(ref.get("conversation_id") or "").strip()
            if cid:
                conversation_ids.add(cid)
            turn = parse_turn_index(str(ref.get("excerpt_pointer") or ""))
            if turn is not None:
                turn_indices.add(turn)
    return conversation_ids, turn_indices


def apply_draft_to_chapters(base_chapters: list[dict[str, Any]], draft: dict[str, Any]) -> list[dict[str, Any]]:
    return overlay_llm_chapters(base_chapters, draft.get("chapters") or [])


def _anthropic_complete(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
    return structured_complete(
        system,
        user,
        schema,
        tool_name="submit_customer_report",
        tool_description="Submit the 14-chapter customer report draft.",
        max_tokens=CLAUDE_STRUCTURED_MAX_TOKENS,
        temperature=0,
    )


def build_synthesis_system_prompt() -> str:
    """ES-30 — role + schema contract + ES-14..27 checklist + tone/guardrails from config."""
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    titles = "\n".join(f"{chapter_id}. {title}" for chapter_id, title in _registry_specs())
    return (
        template
        + "\n\nSCHEMA CONTRACT (CustomerReportDraft — enforced by submit_customer_report tool):\n"
        + _schema_contract_brief()
        + "\n\nCHAPTER TITLES (copy exactly):\n"
        + titles
        + "\n\nCONFIRM GATE (ES-13): Before human confirmation, chapter 6 ai_split must not be contradicted "
        "and must not be duplicated elsewhere — see CROSS-CHAPTER AI CONSISTENCY above.\n"
        + _format_tone_and_guardrails(tone_voice())
        + f"\n\nPinned model: {sonnet_model()}. Temperature: 0."
    )


def _system_prompt() -> str:
    return build_synthesis_system_prompt()


def _schema_contract_brief() -> str:
    schema = load_customer_report_schema()
    required_roots = schema.get("required") or []
    chapter_props = (schema.get("properties") or {}).get("chapters") or {}
    chapter_item = chapter_props.get("items") or {}
    chapter_required = chapter_item.get("required") or []
    ref_props = ((chapter_item.get("properties") or {}).get("source_refs") or {}).get("items") or {}
    ref_required = ref_props.get("required") or []
    lines = [
        f"- Root required fields: {', '.join(required_roots)}",
        f"- Each chapter required: {', '.join(chapter_required)}",
        "- Exactly 14 chapters with ids 0..13; each body is a non-empty block array.",
        f"- Each chapter source_refs entry required: {', '.join(ref_required)}",
        "- cover keys only: tagline, sources_line, how_produced (no extra cover keys).",
        "- open_items item_type: dependency | assumption.",
    ]
    return "\n".join(lines)


def _format_tone_and_guardrails(guide: dict[str, Any]) -> str:
    parts = [
        "STYLE & GUARDRAILS (loaded from config/tone_voice.yaml — never hardcode tone in code):",
        f"Style: {guide.get('style', '')}",
        f"Audience: {guide.get('audience', '')}",
        "",
        "Must:",
    ]
    for item in guide.get("must") or []:
        parts.append(f"- {item}")
    parts.append("")
    parts.append("Must not (guardrails):")
    for item in guide.get("must_not") or []:
        parts.append(f"- {item}")
    return "\n".join(parts)


def _user_prompt(
    skeleton: dict[str, Any],
    engine_outputs: dict[str, Any],
    *,
    client_pack: dict[str, Any] | None = None,
) -> str:
    pack_block = format_client_pack_for_prompt(client_pack or skeleton.get("client_pack"))
    safe_skeleton = {
        key: skeleton[key]
        for key in (
            "opportunity_id",
            "title",
            "department",
            "systems",
            "rules",
            "exceptions",
            "access_needs",
            "open_items",
            "kpis",
            "people",
            "constraints",
            "risks",
            "facts",
            "requirements",
            "unknowns",
            "conversation_ids",
            "stage3_candidates",
            "conflicts",
            "client_pack",
        )
        if key in skeleton
    }
    entries = []
    for entry in skeleton.get("source_entries") or []:
        refs = entry.get("source_refs") or []
        entries.append(
            {
                "bucket": entry.get("bucket"),
                "statement": entry.get("statement"),
                "origin": entry.get("origin"),
                "confidence": entry.get("confidence"),
                "source_refs": refs,
            }
        )
    pack_section = f"{pack_block}\n\n" if pack_block else ""
    return (
        f"prompt_version: {PROMPT_VERSION}\n"
        "Use ONLY these knowledge entries. If a field is missing, write an open_item — do not invent it.\n"
        "If conflicts are listed, keep both values and require clarification — do not pick a winner.\n"
        "Use additional_client_information only when CLIENT_PACK is present; never invent extra pack fields.\n\n"
        f"{pack_section}"
        f"SKELETON:\n{json.dumps(safe_skeleton, ensure_ascii=False, indent=2)}\n\n"
        f"KNOWLEDGE ENTRIES:\n{json.dumps(entries, ensure_ascii=False, indent=2)}\n\n"
        "ENGINE OUTPUTS (copy numbers exactly; do not recalculate):\n"
        f"{json.dumps(engine_outputs, ensure_ascii=False, indent=2)}\n"
    )


def _assert_registry_chapters(draft: dict[str, Any]) -> None:
    expected = _registry_specs()
    actual = [
        (str(chapter.get("chapter_id")), str(chapter.get("title") or "").strip())
        for chapter in draft.get("chapters") or []
    ]
    if actual != expected:
        raise FrameworkSynthesisError(
            "Claude must return exactly 14 chapters with the registry ids and titles, in order."
        )


def _coerce_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Keep Claude extras from failing additionalProperties:false checks."""
    cover = draft.get("cover") if isinstance(draft.get("cover"), dict) else {}
    chapters = []
    for chapter in draft.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        refs = chapter.get("source_refs")
        if isinstance(refs, dict):
            refs = [refs]
        chapters.append(
            {
                "chapter_id": str(chapter.get("chapter_id")),
                "title": str(chapter.get("title") or "").strip(),
                "body": chapter.get("body") if isinstance(chapter.get("body"), list) else [],
                "source_refs": [_coerce_ref(ref) for ref in refs or [] if isinstance(ref, dict)],
            }
        )
    return {
        "title": str(draft.get("title") or "").strip() or "Customer framework report",
        "department": str(draft.get("department") or "").strip() or "Unspecified",
        "cover": {
            "tagline": str(cover.get("tagline") or ""),
            "sources_line": str(cover.get("sources_line") or ""),
            "how_produced": str(cover.get("how_produced") or ""),
        },
        "kpis": [_pick(item, "name", "baseline", "target", "measured_via") for item in _list(draft.get("kpis"))],
        "systems": [_coerce_system(item) for item in _list(draft.get("systems"))],
        "rules": [_pick(item, "name", "logic") for item in _list(draft.get("rules"))],
        "exceptions": [_pick(item, "name", "frequency", "handling") for item in _list(draft.get("exceptions"))],
        "access_needs": [_pick(item, "category", "detail", "status", "owner") for item in _list(draft.get("access_needs"))],
        "open_items": [_coerce_open_item(item) for item in _list(draft.get("open_items"))],
        "chapters": chapters,
    }


def _list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _pick(item: dict[str, Any], *keys: str) -> dict[str, str]:
    return {key: str(item.get(key) or "") for key in keys}


def _coerce_system(item: dict[str, Any]) -> dict[str, str]:
    direction = str(item.get("direction") or "internal").strip().lower().replace("-", "_").replace(" ", "_")
    if direction not in {"read", "write", "read_write", "internal"}:
        direction = "internal"
    status = str(item.get("status") or "available").strip().lower().replace(" ", "_")
    if status not in {"available", "open_dependency"}:
        status = "open_dependency" if "open" in status or "missing" in status else "available"
    return {
        "name": str(item.get("name") or ""),
        "role": str(item.get("role") or ""),
        "direction": direction,
        "access_path": str(item.get("access_path") or ""),
        "data_classification": str(item.get("data_classification") or ""),
        "status": status,
    }


def _coerce_open_item(item: dict[str, Any]) -> dict[str, str]:
    item_type = str(item.get("item_type") or "assumption").strip().lower()
    if item_type not in {"dependency", "assumption"}:
        item_type = "assumption"
    return {
        "description": str(item.get("description") or ""),
        "item_type": item_type,
        "owner": str(item.get("owner") or ""),
        "consequence_if_different": str(item.get("consequence_if_different") or ""),
    }


def _coerce_ref(ref: dict[str, Any]) -> dict[str, str]:
    cid = str(ref.get("conversation_id") or "").strip()
    match = re.fullmatch(r"[Cc]([1-9][0-9]*)", cid)
    if match:
        cid = f"C{match.group(1)}"
    pointer = ref.get("excerpt_pointer")
    if pointer is None:
        pointer = ref.get("turn")
    if isinstance(pointer, int) and not isinstance(pointer, bool):
        pointer = f"turn:{pointer}"
    else:
        text = str(pointer or "").strip()
        found = re.search(r"(\d+)", text)
        pointer = f"turn:{found.group(1)}" if found else text
    return {
        "conversation_id": cid,
        "speaker_role": str(ref.get("speaker_role") or ref.get("speaker") or "").strip(),
        "excerpt_pointer": str(pointer),
    }


def _registry_specs() -> list[tuple[str, str]]:
    registry = json.loads((repo_root() / "packages" / "contracts" / "chapter_registry.json").read_text(encoding="utf-8"))
    return chapter_specs_from_registry(registry)
