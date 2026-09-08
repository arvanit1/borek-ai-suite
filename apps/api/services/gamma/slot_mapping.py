"""JJ-26: fill the named Borek template slots from an opportunity and Framework.

Every chapter-fed slot reads only the chapters the template contract assigns to
it, which are the same chapters the internal renderer allows for the matching
layout. Slots with no grounded content are omitted rather than padded, so a thin
Framework produces a shorter deck instead of invented copy.
"""

from __future__ import annotations

from typing import Any, Iterable

from services.gamma.contract import GammaContentSlot, GammaPayloadError
from services.gamma.template import GammaSlotDefinition, GammaTemplate, load_gamma_template

_PARAGRAPH_SEPARATOR = "\n\n"


def build_gamma_content_slots(
    *,
    opportunity: dict[str, Any],
    framework: dict[str, Any] | None = None,
    template: GammaTemplate | None = None,
) -> tuple[GammaContentSlot, ...]:
    """Return the populated slots for one client, in template card order."""
    contract = template or load_gamma_template()
    chapters = _chapters_by_id(framework)
    filled: list[GammaContentSlot] = []
    for definition in contract.slots:
        value = _slot_value(definition, opportunity=opportunity, chapters=chapters)
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


def _slot_value(
    definition: GammaSlotDefinition,
    *,
    opportunity: dict[str, Any],
    chapters: dict[str, Any],
) -> str:
    if definition.is_chapter_fed:
        parts = [
            body
            for chapter_id in definition.source_chapter_ids
            if (body := _chapter_body(chapters.get(chapter_id)))
        ]
        return _PARAGRAPH_SEPARATOR.join(parts)
    if definition.source.startswith("opportunity."):
        field = definition.source.split(".", 1)[1]
        return str(opportunity.get(field) or "").strip()
    raise GammaPayloadError(
        f"Slot '{definition.name}' declares an unknown source '{definition.source}'."
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


def _chapter_body(chapter: Any) -> str:
    if not isinstance(chapter, dict):
        return ""
    return _flatten_body(chapter.get("body")).strip()


def _flatten_body(body: Any) -> str:
    """Chapter bodies are prose or structured blocks; both become plain text."""
    if isinstance(body, str):
        return body.strip()
    if isinstance(body, list):
        return "\n".join(part for item in body if (part := _flatten_body(item)))
    if isinstance(body, dict):
        return "\n".join(part for value in body.values() if (part := _flatten_body(value)))
    if isinstance(body, (int, float)):
        return str(body)
    return ""


def _clamp(value: str, max_chars: int) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    cut = max(window.rfind(". "), window.rfind("\n"))
    if cut < max_chars // 2:
        cut = window.rfind(" ")
    return (window[: cut + 1] if cut > 0 else window).strip()
