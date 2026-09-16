"""Load the Borek presentation CI contract from packages/contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "contracts" / "presentation_ci.json"
)


class PresentationCIContractError(RuntimeError):
    """The presentation CI contract on disk is unusable."""


@lru_cache(maxsize=1)
def load_presentation_ci() -> dict[str, Any]:
    if not _CONTRACT_PATH.is_file():
        raise PresentationCIContractError(f"Missing CI contract at {_CONTRACT_PATH}")
    payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PresentationCIContractError("presentation_ci.json must be an object.")
    theme_id = str(payload.get("official_gamma_theme_id") or "").strip()
    if not theme_id:
        raise PresentationCIContractError("official_gamma_theme_id is required.")
    return payload


def official_gamma_theme_id() -> str:
    return str(load_presentation_ci()["official_gamma_theme_id"])


def banned_marketing_terms() -> tuple[str, ...]:
    voice = load_presentation_ci().get("voice") or {}
    terms = voice.get("banned_marketing_terms") or []
    if not isinstance(terms, list) or not terms:
        raise PresentationCIContractError("voice.banned_marketing_terms is required.")
    return tuple(str(term) for term in terms)


def ci_voice_instruction_block() -> str:
    """Shared Stage B copy guidance for planner and slide generators."""
    ci = load_presentation_ci()
    voice = ci.get("voice") or {}
    editorial = ci.get("editorial") or {}
    banned = ", ".join(banned_marketing_terms())
    lines = [
        "Follow Borek presentation CI voice:",
        "- Write clear, reliable, concrete copy in active voice with short sentences.",
        "- One clear idea per slide; concise titles that state the takeaway, not just the topic.",
        "- SUCCESS_METRICS and other KPI/data slides must lead with the conclusion in the title.",
        "- Prefer concrete numbers over adjectives; keep metrics Framework-grounded.",
        "- Include dates on commitments when the source material supports them.",
        "- Do not invent facts, dates, or numbers.",
        f"- Never use these banned marketing terms: {banned}.",
        "- No exclamation marks and no emoji in customer-facing slide text.",
        "- Do not specify colors, fonts, layout geometry, or other visual CI in SlideSpec content.",
    ]
    if editorial.get("clear_next_actions"):
        lines.append("- End with clear next actions where the layout supports them.")
    return " ".join(lines)
