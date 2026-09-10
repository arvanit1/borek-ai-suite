"""JJ-26 slots filled by ES-40 / JJ-31: confirmed Framework plus retrieved facts.

Every chapter-fed slot reads only the chapters the stage profile assigns to
it. Retrieved Borek facts are included when those chapters are in the slot's
allowance and the profile lists that fact kind. Chapter 9 pricing never fills
a layout slot (MS-14); ES-40 carries grounded prices on the payload for
Concretisation instead. Empty slots are omitted, not padded — except when a
later stage reuses confirmed copy from the stage before it.
"""

from __future__ import annotations

from typing import Any, Iterable

from services.framework.company_facts import (
    UngroundedPriceError,
    format_company_fact_line,
    live_answered_lookups,
    refuse_ungrounded_prices,
)
from services.gamma.contract import FORBIDDEN_BRANDING_KEYS, GammaContentSlot, GammaPayloadError
from services.gamma.template import GammaSlotDefinition, GammaTemplate, load_gamma_template

JOURNEY_STAGES = ("first_contact", "deepening", "concretisation")
DEFAULT_JOURNEY_STAGE = "deepening"

JOURNEY_STAGES = ("first_contact", "deepening", "concretisation")
DEFAULT_JOURNEY_STAGE = "deepening"

_PARAGRAPH_SEPARATOR = "\n\n"
_SKIP_KEYS = frozenset(
    {
        "source_refs",
        "conversation_id",
        "excerpt_pointer",
        "speaker_role",
        "origin",
        "chapter_id",
        "block",
        "id",
        "kind",
        "from",
        "to",
        "confidence",
        "bucket",
        "caption",
    }
)
_FACT_KINDS_FOR_CHAPTER = {
    "4": frozenset({"service", "reference"}),
    "10": frozenset({"staffing"}),
}


def resolve_journey_stage(stage: str | None) -> str:
    allowed = tuple(load_gamma_template().stage_profiles) or JOURNEY_STAGES
    value = str(stage or "").strip()
    if not value:
        raise GammaPayloadError(
            "Journey stage is required. "
            f"Expected one of: {', '.join(allowed)}."
        )
    if value not in allowed:
        raise GammaPayloadError(
            f"Unknown journey stage '{stage}'. "
            f"Expected one of: {', '.join(allowed)}."
        )
    return value


def build_gamma_content_slots(
    *,
    opportunity: dict[str, Any],
    framework: dict[str, Any] | None = None,
    template: GammaTemplate | None = None,
    stage: str = DEFAULT_JOURNEY_STAGE,
    prior_stage_context: dict[str, Any] | None = None,
) -> tuple[GammaContentSlot, ...]:
    """Return the populated content slots for one client, in template card order."""
    resolved_stage = resolve_journey_stage(stage)
    contract = template or load_gamma_template()
    profile = contract.profile(resolved_stage)
    payload = _framework_payload(framework)
    _require_confirmed(payload)
    chapters = _chapters_by_id(payload)
    stage_slots = contract.slots_for_stage(resolved_stage)
    filled_by_name: dict[str, GammaContentSlot] = {}
    for definition in stage_slots:
        if definition.name in FORBIDDEN_BRANDING_KEYS or definition.name.startswith("brand."):
            continue
        value = _slot_value(
            definition,
            opportunity=opportunity,
            chapters=chapters,
            framework=payload,
            profile_fact_kinds=profile.fact_kinds,
            pricing_permitted=profile.pricing_permitted,
        )
        if value:
            filled_by_name[definition.name] = GammaContentSlot(
                definition.name, _clamp(value, definition.max_chars)
            )
    _carry_forward_slots(
        filled_by_name,
        stage_slots=stage_slots,
        prior_stage_context=prior_stage_context,
    )
    filled: list[GammaContentSlot] = []
    for definition in stage_slots:
        slot = filled_by_name.get(definition.name)
        if slot is not None:
            filled.append(slot)
            continue
        if definition.required:
            raise GammaPayloadError(
                f"Required Borek template slot '{definition.name}' has no content."
            )
    blob = " ".join(slot.value for slot in filled)
    company_facts = ((payload or {}).get("generation_meta") or {}).get("company_facts")
    try:
        refuse_ungrounded_prices(
            text=blob,
            grounding=company_facts,
            allow_prices=False,
        )
        if profile.pricing_permitted:
            refuse_ungrounded_prices(
                text=_chapter_body(chapters.get("9")),
                grounding=company_facts,
                allow_prices=True,
            )
    except UngroundedPriceError as exc:
        raise GammaPayloadError(str(exc)) from exc
    return tuple(filled)


def slot_chapter_provenance(
    slots: Iterable[GammaContentSlot],
    *,
    template: GammaTemplate | None = None,
    stage: str = DEFAULT_JOURNEY_STAGE,
) -> dict[str, tuple[str, ...]]:
    """Which Framework chapters each sent slot was allowed to draw from."""
    contract = template or load_gamma_template()
    resolved = resolve_journey_stage(stage)
    definitions = {definition.name: definition for definition in contract.slots_for_stage(resolved)}
    return {
        slot.name: definitions[slot.name].source_chapter_ids
        if slot.name in definitions
        else contract.slot(slot.name).source_chapter_ids
        for slot in slots
    }


def _framework_payload(framework: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(framework, dict):
        return None
    inner = framework.get("framework_json")
    if isinstance(inner, dict) and inner.get("chapters") is not None:
        payload = dict(inner)
        if payload.get("status") is None and framework.get("status") is not None:
            payload["status"] = framework["status"]
        if payload.get("generation_meta") is None and framework.get("generation_meta") is not None:
            payload["generation_meta"] = framework["generation_meta"]
        return payload
    return framework


def _require_confirmed(framework: dict[str, Any] | None) -> None:
    if not framework:
        return
    if not framework.get("chapters"):
        return
    if str(framework.get("status") or "").strip().lower() != "confirmed":
        raise GammaPayloadError("Gamma content payload requires a confirmed Framework.")


def _slot_value(
    definition: GammaSlotDefinition,
    *,
    opportunity: dict[str, Any],
    chapters: dict[str, Any],
    framework: dict[str, Any] | None,
    profile_fact_kinds: frozenset[str],
    pricing_permitted: bool,
) -> str:
    if definition.source.startswith("opportunity."):
        field = definition.source.split(".", 1)[1]
        return str(opportunity.get(field) or "").strip()
    if not definition.is_chapter_fed:
        raise GammaPayloadError(
            f"Slot '{definition.name}' declares an unknown source '{definition.source}'."
        )
    if definition.name == "cover.subtitle":
        tagline = str(((framework or {}).get("cover") or {}).get("tagline") or "").strip()
        if tagline:
            return tagline
        return _first_prose(chapters.get("1"))
    parts = [
        body
        for chapter_id in definition.source_chapter_ids
        if (body := _chapter_body(chapters.get(chapter_id)))
    ]
    retrieved = _retrieved_facts_text(
        framework,
        definition.source_chapter_ids,
        profile_fact_kinds=profile_fact_kinds,
        pricing_permitted=pricing_permitted,
    )
    if retrieved:
        blob = _PARAGRAPH_SEPARATOR.join(parts)
        extras = [line for line in retrieved.split("\n") if line and line not in blob]
        if extras:
            parts.append("\n".join(extras))
    return _PARAGRAPH_SEPARATOR.join(part for part in parts if part)


def _retrieved_facts_text(
    framework: dict[str, Any] | None,
    chapter_ids: tuple[str, ...],
    *,
    profile_fact_kinds: frozenset[str],
    pricing_permitted: bool,
) -> str:
    kinds: set[str] = set()
    for chapter_id in chapter_ids:
        kinds.update(_FACT_KINDS_FOR_CHAPTER.get(chapter_id) or ())
    kinds &= set(profile_fact_kinds)
    if not kinds:
        return ""
    meta = ((framework or {}).get("generation_meta") or {}).get("company_facts") or {}
    lines: list[str] = []
    for lookup in live_answered_lookups(
        meta,
        kinds=kinds,
        include_pricing=pricing_permitted,
    ):
        kind = str(lookup.get("kind") or "")
        if kind == "pricing":
            continue
        line = format_company_fact_line(lookup)
        if line:
            lines.append(line)
    return "\n".join(lines)


def _carry_forward_slots(
    filled_by_name: dict[str, GammaContentSlot],
    *,
    stage_slots: tuple[GammaSlotDefinition, ...],
    prior_stage_context: dict[str, Any] | None,
) -> None:
    """BT-31 handoff: fill profile slots the current Framework left empty from the prior stage."""
    if not prior_stage_context:
        return
    prior_values = {
        str(item.get("name")): str(item.get("value") or "").strip()
        for item in (prior_stage_context.get("slots") or [])
        if isinstance(item, dict) and item.get("name") and str(item.get("value") or "").strip()
    }
    if not prior_values:
        return
    for definition in stage_slots:
        if definition.name in filled_by_name:
            continue
        prior = prior_values.get(definition.name)
        if not prior:
            continue
        filled_by_name[definition.name] = GammaContentSlot(
            definition.name, _clamp(prior, definition.max_chars)
        )


def _chapters_by_id(framework: dict[str, Any] | None) -> dict[str, Any]:
    chapters = (framework or {}).get("chapters") or []
    if not isinstance(chapters, list):
        return {}
    return {
        str(chapter.get("chapter_id")): chapter
        for chapter in chapters
        if isinstance(chapter, dict) and chapter.get("chapter_id") is not None
    }


def _first_prose(chapter: Any) -> str:
    if not isinstance(chapter, dict):
        return ""
    body = chapter.get("body")
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, list):
        for item in body:
            if isinstance(item, dict) and item.get("block") == "prose":
                text = str(item.get("text") or "").strip()
                if text:
                    return text
        return _flatten_body(body).strip()
    return _flatten_body(body).strip()


def _chapter_body(chapter: Any) -> str:
    if not isinstance(chapter, dict):
        return ""
    return _flatten_body(chapter.get("body")).strip()


def _flatten_body(body: Any) -> str:
    """Turn chapter prose or typed blocks into customer text. No layout keys."""
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, list):
        return "\n".join(part for item in body if (part := _flatten_body(item)))
    if isinstance(body, dict):
        typed = _flatten_typed_block(body)
        if typed is not None:
            return typed
        return "\n".join(
            part
            for key, value in body.items()
            if str(key) not in _SKIP_KEYS and (part := _flatten_body(value))
        )
    if isinstance(body, (int, float)):
        return str(body)
    return ""


def _flatten_typed_block(block: dict[str, Any]) -> str | None:
    kind = str(block.get("block") or "")
    if not kind:
        return None
    if kind in {"prose", "callout"}:
        return str(block.get("text") or "").strip()
    if kind == "bullets":
        return "\n".join(str(item).strip() for item in block.get("items") or [] if str(item).strip())
    if kind == "kv_rows":
        rows = []
        for row in block.get("rows") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "").strip()
            value = str(row.get("value") or "").strip()
            if label and value:
                rows.append(f"{label}: {value}")
            elif value:
                rows.append(value)
        return "\n".join(rows)
    if kind == "table":
        lines = [" | ".join(str(col) for col in block.get("columns") or [])]
        for row in block.get("rows") or []:
            if isinstance(row, list):
                lines.append(" | ".join(str(cell) for cell in row))
        return "\n".join(line for line in lines if line.strip())
    if kind == "process_flow":
        return "\n".join(
            str(node.get("label") or "").strip()
            for node in block.get("nodes") or []
            if isinstance(node, dict) and str(node.get("label") or "").strip()
        )
    if kind == "timeline":
        lines = []
        for week in block.get("weeks") or []:
            if not isinstance(week, dict):
                continue
            label = str(week.get("id") or "").strip()
            items = [str(item).strip() for item in week.get("items") or [] if str(item).strip()]
            if label and items:
                lines.append(f"{label}: {'; '.join(items)}")
            elif items:
                lines.extend(items)
        return "\n".join(lines)
    if kind == "score_bars":
        return "\n".join(
            f"{item.get('name')}: {item.get('score')}"
            for item in block.get("items") or []
            if isinstance(item, dict) and item.get("name") is not None
        )
    if kind == "glossary":
        return "\n".join(
            f"{item.get('term')}: {item.get('meaning')}"
            for item in block.get("terms") or []
            if isinstance(item, dict) and item.get("term")
        )
    if kind == "sensitivity":
        return "\n".join(
            f"{row.get('label')}: {row.get('detail')}"
            for row in block.get("rows") or []
            if isinstance(row, dict)
        )
    if kind == "ai_split":
        used = [str(item) for item in block.get("used_for") or [] if str(item).strip()]
        not_used = [str(item) for item in block.get("not_used_for") or [] if str(item).strip()]
        parts = []
        if used:
            parts.append("AI is used for: " + "; ".join(used))
        if not_used:
            parts.append("AI is not used for: " + "; ".join(not_used))
        return "\n".join(parts)
    return None


def _clamp(value: str, max_chars: int) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    cut = max(window.rfind(". "), window.rfind("\n"))
    if cut < max_chars // 2:
        cut = window.rfind(" ")
    return (window[: cut + 1] if cut > 0 else window).strip()
