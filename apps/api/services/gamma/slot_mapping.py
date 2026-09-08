"""JJ-26 slots filled by ES-40: confirmed Framework plus retrieved facts, content only.

Every chapter-fed slot reads only the chapters the template contract assigns to
it. Retrieved Borek facts are included when those chapters are in the slot's
allowance — never chapter 9 pricing (MS-14). Empty slots are omitted, not padded.
"""

from __future__ import annotations

from typing import Any, Iterable

from services.framework.company_facts import format_company_fact_line
from services.gamma.contract import FORBIDDEN_BRANDING_KEYS, GammaContentSlot, GammaPayloadError
from services.gamma.template import GammaSlotDefinition, GammaTemplate, load_gamma_template

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


def build_gamma_content_slots(
    *,
    opportunity: dict[str, Any],
    framework: dict[str, Any] | None = None,
    template: GammaTemplate | None = None,
) -> tuple[GammaContentSlot, ...]:
    """Return the populated content slots for one client, in template card order."""
    contract = template or load_gamma_template()
    payload = _framework_payload(framework)
    _require_confirmed(payload)
    chapters = _chapters_by_id(payload)
    filled: list[GammaContentSlot] = []
    for definition in contract.slots:
        if definition.name in FORBIDDEN_BRANDING_KEYS or definition.name.startswith("brand."):
            continue
        value = _slot_value(
            definition,
            opportunity=opportunity,
            chapters=chapters,
            framework=payload,
        )
        if not value:
            if definition.required:
                raise GammaPayloadError(
                    f"Required Borek template slot '{definition.name}' has no content."
                )
            continue
        filled.append(GammaContentSlot(definition.name, _clamp(value, definition.max_chars)))
    return tuple(filled)


def slot_chapter_provenance(
    slots: Iterable[GammaContentSlot],
    *,
    template: GammaTemplate | None = None,
) -> dict[str, tuple[str, ...]]:
    """Which Framework chapters each sent slot was allowed to draw from."""
    contract = template or load_gamma_template()
    return {slot.name: contract.slot(slot.name).source_chapter_ids for slot in slots}


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
    retrieved = _retrieved_facts_text(framework, definition.source_chapter_ids)
    if retrieved:
        blob = _PARAGRAPH_SEPARATOR.join(parts)
        extras = [line for line in retrieved.split("\n") if line and line not in blob]
        if extras:
            parts.append("\n".join(extras))
    return _PARAGRAPH_SEPARATOR.join(part for part in parts if part)


def _retrieved_facts_text(framework: dict[str, Any] | None, chapter_ids: tuple[str, ...]) -> str:
    kinds: set[str] = set()
    for chapter_id in chapter_ids:
        kinds.update(_FACT_KINDS_FOR_CHAPTER.get(chapter_id) or ())
    if not kinds:
        return ""
    meta = ((framework or {}).get("generation_meta") or {}).get("company_facts") or {}
    lines: list[str] = []
    for lookup in meta.get("answered") or meta.get("lookups") or []:
        if str(lookup.get("status") or "") != "answered":
            continue
        kind = str(lookup.get("kind") or "")
        if kind not in kinds or kind == "pricing":
            continue
        line = format_company_fact_line(lookup)
        if line:
            lines.append(line)
    return "\n".join(lines)


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
