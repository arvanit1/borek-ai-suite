"""Provider-specific Gamma payload compliance for non-pricing journey stages.

SlideSpecs are validated for commercial content at generation time, but the
live Gamma payload is built from confirmed Framework chapter prose. Chapter
tables and business-case rows can therefore reach Gamma slots with monetary
values that ES-39 refuses on first_contact/deepening payloads.

This module repairs slot text at the Gamma boundary only. Persisted Framework
and SlideSpec data remain unchanged.
"""

from __future__ import annotations

import re
from typing import Any

from services.framework.company_facts import (
    UngroundedPriceError,
    rate_card_amounts_in_text,
    refuse_ungrounded_prices,
)
from services.gamma.contract import GammaContentSlot, GammaPayloadError

_PARAGRAPH_SEPARATOR = "\n\n"
_CURRENCY_TEXT = re.compile(
    r"(?:[€£$]|\b(?:EUR|USD|GBP|CHF|PLN)\b|\b(?:euros?|dollars?|pounds?)\b)",
    re.IGNORECASE,
)
_COMMERCIAL_TERM = re.compile(
    r"\b(?:investment|monetary|payback|pricing?|revenue|roi|return\s+on\s+investment|budget|build\s+cost|run\s+cost|net\s+value)\b",
    re.IGNORECASE,
)
_COST_OR_SAVINGS = re.compile(r"\b(?:costs?|savings?)\b", re.IGNORECASE)
_NUMBER_TOKEN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])")


def contains_prohibited_gamma_commercial_text(text: str) -> bool:
    """True when text carries monetary/commercial content prohibited for non-pricing stages."""
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if rate_card_amounts_in_text(normalized):
        return True
    if _CURRENCY_TEXT.search(normalized):
        return True
    if _COMMERCIAL_TERM.search(normalized):
        return True
    return bool(_COST_OR_SAVINGS.search(normalized) and _NUMBER_TOKEN.search(normalized))


def repair_gamma_slot_text(text: str) -> str:
    """Remove monetary/commercial fragments from one slot value."""
    normalized = str(text or "").strip()
    if not normalized or not contains_prohibited_gamma_commercial_text(normalized):
        return normalized

    kept_paragraphs: list[str] = []
    for paragraph in normalized.split(_PARAGRAPH_SEPARATOR):
        kept_lines = [
            line.strip()
            for line in paragraph.splitlines()
            if line.strip() and not contains_prohibited_gamma_commercial_text(line)
        ]
        if kept_lines:
            kept_paragraphs.append("\n".join(kept_lines))
    return _PARAGRAPH_SEPARATOR.join(kept_paragraphs).strip()


def apply_gamma_payload_compliance(
    slots: tuple[GammaContentSlot, ...],
    *,
    pricing_permitted: bool,
) -> tuple[GammaContentSlot, ...]:
    """Repair slot values when the stage profile forbids pricing/commercial content."""
    if pricing_permitted:
        return slots
    repaired: list[GammaContentSlot] = []
    for slot in slots:
        value = repair_gamma_slot_text(slot.value)
        if value != slot.value:
            repaired.append(GammaContentSlot(slot.name, value))
        else:
            repaired.append(slot)
    return tuple(repaired)


def find_prohibited_gamma_commercial_paths(payload: dict[str, Any]) -> list[str]:
    """Return dotted paths to slot values still containing prohibited content."""
    hits: list[str] = []
    for index, slot in enumerate(payload.get("slots") or []):
        if not isinstance(slot, dict):
            continue
        value = str(slot.get("value") or "")
        if contains_prohibited_gamma_commercial_text(value):
            name = str(slot.get("name") or index)
            hits.append(f"slots[{index}].value ({name})")
    return hits


def validate_gamma_payload_compliance(
    payload: dict[str, Any],
    *,
    pricing_permitted: bool,
    grounding: dict[str, Any] | None,
) -> None:
    """Fail locally when a non-pricing payload still contains prohibited commercial text."""
    remaining = find_prohibited_gamma_commercial_paths(payload)
    if remaining and not pricing_permitted:
        raise GammaPayloadError(
            "Gamma payload still contains prohibited commercial content at "
            + remaining[0]
        )

    blob = " ".join(
        str(item.get("value") or "")
        for item in payload.get("slots") or []
        if isinstance(item, dict)
    )
    try:
        refuse_ungrounded_prices(
            text=blob,
            grounding=grounding,
            allow_prices=pricing_permitted,
        )
    except UngroundedPriceError as exc:
        raise GammaPayloadError(str(exc)) from exc
