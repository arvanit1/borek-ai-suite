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


def _unwrap_localized_payload(view: dict[str, Any]) -> dict[str, Any]:
    """Normalize ES-32 payloads that nest the report under tool-parameter keys."""
    if isinstance(view.get("chapters"), list):
        return view
    for key in ("localized_json", "localized_report", "report"):
        nested = view.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("chapters"), list):
            return _merge_localized_shell(view, nested)
    for key, nested in view.items():
        if key in {"render_language", "customer_only", "status", "change_log", "updated_at", "cover"}:
            continue
        if isinstance(nested, dict) and isinstance(nested.get("chapters"), list):
            return _merge_localized_shell(view, nested)
    return view


def _merge_localized_shell(shell: dict[str, Any], nested: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(nested)
    merged["render_language"] = shell.get("render_language") or merged.get("render_language") or "de"
    merged["customer_only"] = shell.get("customer_only", True)
    if shell.get("status"):
        merged["status"] = shell["status"]
    if shell.get("updated_at"):
        merged["updated_at"] = shell["updated_at"]
    if shell.get("change_log"):
        merged["change_log"] = shell["change_log"]
    if shell.get("cover"):
        merged["cover"] = {**(merged.get("cover") or {}), **shell["cover"]}
    return merged


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


def presentation_render_language(framework: dict[str, Any]) -> str:
    """Language for customer-facing presentation content (ES-32 render language)."""
    customer_view = framework.get("customer_view") or {}
    lang = str(
        customer_view.get("render_language")
        or framework.get("language")
        or "en"
    ).lower()
    return "de" if lang.startswith("de") else "en"


def presentation_chapter_excerpt(framework: dict[str, Any], chapter_id: str) -> dict[str, Any]:
    """Localized title/body for one chapter without mutating the canonical FrameworkObject."""
    canonical = next(
        chapter
        for chapter in framework.get("chapters") or []
        if str(chapter.get("chapter_id")) == str(chapter_id)
    )
    if presentation_render_language(framework) == "en":
        return {
            "chapter_id": str(chapter_id),
            "title": canonical.get("title"),
            "body": copy.deepcopy(canonical.get("body") or []),
        }
    customer = resolve_customer_view(framework, lang="de")
    localized = next(
        (
            chapter
            for chapter in customer.get("chapters") or []
            if str(chapter.get("chapter_id")) == str(chapter_id)
        ),
        None,
    )
    if not isinstance(localized, dict):
        localized = {}
    return {
        "chapter_id": str(chapter_id),
        "title": localized.get("title") or canonical.get("title"),
        "body": copy.deepcopy(localized.get("body") or canonical.get("body") or []),
    }


def localized_planning_chapters(framework: dict[str, Any]) -> list[dict[str, Any]]:
    """Customer-facing chapter excerpts for BT-1 when render language is not English."""
    if presentation_render_language(framework) == "en":
        return []
    return [
        presentation_chapter_excerpt(framework, str(chapter.get("chapter_id")))
        for chapter in framework.get("chapters") or []
        if isinstance(chapter, dict) and chapter.get("chapter_id") is not None
    ]


def resolve_customer_view(
    framework: dict[str, Any],
    *,
    lang: str = "en",
    localize: ClaudeComplete | None = None,
) -> dict[str, Any]:
    """Return a customer view for rendering, localizing on demand for DE (ES-32)."""
    cached = framework.get("customer_view")
    if lang == "de":
        needs_localize = (
            not isinstance(cached, dict)
            or str(cached.get("render_language") or "en") != "de"
            or _localized_view_still_english(framework, cached)
        )
        if needs_localize:
            if localize is None:
                from services.framework.localization import make_localize_fn

                localize = make_localize_fn(
                    opportunity_id=str(framework.get("opportunity_id") or ""),
                    framework_id=str(framework.get("id") or framework.get("framework_id") or ""),
                )
            return build_customer_view(
                framework,
                lang="de",
                localize=localize,
                opportunity_id=str(framework.get("opportunity_id") or ""),
                framework_id=str(framework.get("id") or framework.get("framework_id") or ""),
            )
    if cached:
        return _unwrap_localized_payload(cached)
    return build_customer_view(framework, lang=lang, localize=localize)


def _localized_view_still_english(framework: dict[str, Any], view: dict[str, Any]) -> bool:
    """Detect customer_view tagged DE but still carrying canonical English chapter titles."""
    view = _unwrap_localized_payload(view)
    canonical_titles = {
        str(chapter.get("chapter_id")): chapter.get("title")
        for chapter in framework.get("chapters") or []
        if isinstance(chapter, dict)
    }
    chapters = view.get("chapters") or []
    if not chapters:
        return True
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id"))
        if chapter_id in canonical_titles and chapter.get("title") == canonical_titles[chapter_id]:
            return True
    return False


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
    localized = _unwrap_localized_payload(localized)
    localized["render_language"] = "de"
    localized["customer_only"] = True
    return localized
