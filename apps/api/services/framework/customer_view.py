"""Customer view: citation-stripped, locale-formatted numbers, optional DE localization."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

from services.framework.config_loader import glossary
from services.framework.guardrails import strip_citations_from_value

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "llm" / "claude" / "prompts" / "localize_v1.txt"

ClaudeComplete = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def build_customer_view(
    framework: dict[str, Any],
    *,
    lang: str = "en",
    localize: ClaudeComplete | None = None,
    opportunity_id: str | None = None,
    framework_id: str | None = None,
) -> dict[str, Any]:
    view = copy.deepcopy(framework)
    view.pop("source_entries", None)
    view.pop("numbers", None)
    for chapter in view.get("chapters") or []:
        if isinstance(chapter, dict):
            chapter.pop("source_refs", None)
            for block in chapter.get("body") or []:
                if isinstance(block, dict):
                    block.pop("source_refs", None)
    view = strip_citations_from_value(view)
    view["render_language"] = lang
    view["customer_only"] = True
    if lang == "de":
        view = _localize_de(view, localize=localize)
    return view


def resolve_customer_view(
    framework: dict[str, Any],
    *,
    lang: str = "en",
    localize: ClaudeComplete | None = None,
) -> dict[str, Any]:
    """Return a customer view for rendering, localizing on demand for DE (ES-32)."""
    cached = framework.get("customer_view")
    if lang == "de" and str((cached or {}).get("render_language") or "en") != "de":
        if localize is None:
            from services.framework.localization import make_localize_fn

            localize = make_localize_fn(
                opportunity_id=str(framework.get("opportunity_id") or ""),
                framework_id=str(framework.get("id") or framework.get("framework_id") or ""),
            )
        return build_customer_view(framework, lang="de", localize=localize)
    if cached:
        return cached
    return build_customer_view(framework, lang=lang, localize=localize)


def _localize_de(view: dict[str, Any], *, localize: ClaudeComplete | None) -> dict[str, Any]:
    if localize is None:
        return view
    terms = glossary()
    system = _PROMPT_PATH.read_text(encoding="utf-8")
    user = (
        "Target language: German (DE).\n"
        f"Untranslated tokens: {json.dumps(terms.get('untranslated', []), ensure_ascii=False)}\n"
        f"Terminology table: {json.dumps(terms.get('de', {}), ensure_ascii=False)}\n"
        "JSON:\n"
        + json.dumps(view, ensure_ascii=False)
    )
    localized = localize(system, user, {"type": "object"})
    if not isinstance(localized, dict):
        return view
    localized["render_language"] = "de"
    localized["customer_only"] = True
    return localized
