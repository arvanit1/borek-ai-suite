"""Gamma scratch inputText: one card per layout with explicit card breaks."""

from __future__ import annotations

from typing import Any, Iterable

from services.gamma.contract import GammaContentSlot
from services.gamma.template import GammaTemplate, load_gamma_template

CARD_BREAK = "\n---\n"
CARD_SPLIT_INPUT_TEXT_BREAKS = "inputTextBreaks"

_SKIP_SLIDE_SPEC_KEYS = frozenset(
    {
        "layoutId",
        "slideId",
        "sourceChapterIds",
        "fieldProvenance",
        "schema_version",
    }
)


def align_slots_with_planned_slides(
    slots: Iterable[GammaContentSlot],
    slide_specs: Iterable[dict[str, Any]] | None,
    *,
    template: GammaTemplate | None = None,
) -> tuple[GammaContentSlot, ...]:
    """Order outbound slots by persisted SlideSpecs and fill gaps from slide text."""
    resolved_specs = tuple(spec for spec in (slide_specs or ()) if isinstance(spec, dict))
    if not resolved_specs:
        return tuple(slots)

    contract = template or load_gamma_template()
    slots_by_layout: dict[str, list[GammaContentSlot]] = {}
    for slot in slots:
        layout_id = contract.slot(slot.name).layout_id
        slots_by_layout.setdefault(layout_id, []).append(slot)

    aligned: list[GammaContentSlot] = []
    seen_names: set[str] = set()
    for spec in resolved_specs:
        layout_id = str(spec.get("layoutId") or "")
        layout_slots = slots_by_layout.get(layout_id, [])
        if layout_slots:
            for slot in layout_slots:
                if slot.name in seen_names:
                    continue
                aligned.append(slot)
                seen_names.add(slot.name)
            continue
        fallback = slide_spec_preservable_text(spec)
        for card in contract.cards:
            if card.layout_id != layout_id:
                continue
            for slot_name in card.slots:
                if slot_name in seen_names:
                    continue
                aligned.append(GammaContentSlot(slot_name, fallback))
                seen_names.add(slot_name)
            break
    return tuple(aligned)


def build_card_segments(
    slots: Iterable[GammaContentSlot],
    *,
    template: GammaTemplate | None = None,
    planned_slide_specs: Iterable[dict[str, Any]] | None = None,
) -> tuple[str, ...]:
    """Return one preserve-mode card segment per layout, in deck order."""
    ordered_slots = align_slots_with_planned_slides(
        slots,
        planned_slide_specs,
        template=template,
    )
    contract = template or load_gamma_template()
    planned_layouts = [
        str(spec.get("layoutId") or "")
        for spec in (planned_slide_specs or ())
        if isinstance(spec, dict) and spec.get("layoutId")
    ]
    if planned_layouts:
        layout_order = planned_layouts
    else:
        layout_order = []
        seen: set[str] = set()
        for slot in ordered_slots:
            layout_id = contract.slot(slot.name).layout_id
            if layout_id in seen:
                continue
            layout_order.append(layout_id)
            seen.add(layout_id)

    slots_by_layout: dict[str, list[GammaContentSlot]] = {}
    for slot in ordered_slots:
        layout_id = contract.slot(slot.name).layout_id
        slots_by_layout.setdefault(layout_id, []).append(slot)

    segments: list[str] = []
    for layout_id in layout_order:
        card_slots = slots_by_layout.get(layout_id, [])
        if not card_slots:
            continue
        segments.append(
            "\n\n".join(f"{slot.name}: {slot.value}" for slot in card_slots if slot.value.strip())
        )
    return tuple(segment for segment in segments if segment.strip())


def build_scratch_input_text(
    slots: Iterable[GammaContentSlot],
    *,
    template: GammaTemplate | None = None,
    planned_slide_specs: Iterable[dict[str, Any]] | None = None,
) -> tuple[str, int]:
    """Build inputText and the card count Gamma must honour via inputTextBreaks."""
    segments = build_card_segments(
        slots,
        template=template,
        planned_slide_specs=planned_slide_specs,
    )
    if not segments:
        flat = "\n\n".join(
            f"{slot.name}: {slot.value}" for slot in slots if slot.value.strip()
        )
        return flat, 1 if flat.strip() else 0
    return CARD_BREAK.join(segments), len(segments)


def slide_spec_preservable_text(slide_spec: dict[str, Any]) -> str:
    """Flatten persisted SlideSpec content for textMode=preserve without layout keys."""
    parts: list[str] = []
    for key, value in slide_spec.items():
        if key in _SKIP_SLIDE_SPEC_KEYS:
            continue
        parts.extend(_flatten_preservable_value(str(key), value))
    if parts:
        return "\n\n".join(parts)
    layout_id = str(slide_spec.get("layoutId") or "UNKNOWN")
    return f"layoutId: {layout_id}"


def _flatten_preservable_value(prefix: str, value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [f"{prefix}: {text}"] if text else []
    if isinstance(value, (int, float)):
        return [f"{prefix}: {value}"]
    if isinstance(value, list):
        lines: list[str] = []
        for index, item in enumerate(value):
            lines.extend(_flatten_preservable_value(f"{prefix}[{index}]", item))
        return lines
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            lines.extend(_flatten_preservable_value(f"{prefix}.{key}", item))
        return lines
    return []
