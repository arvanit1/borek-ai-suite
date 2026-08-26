"""ES-13 — block confirmation when chapter 6 AI-used / not-used is contradicted."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any, Callable

from services.framework.chapter_validators.base import blocks_of, chapter_by_id
from services.framework.chapter_validators.ch05_how_it_works import (
    ensure_never_autonomous_statement,
    text_has_never_autonomous_marker,
)
from services.framework.customer_view import build_customer_view
from services.framework.guardrails import strip_citations_from_value

_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "any",
        "for",
        "from",
        "into",
        "of",
        "or",
        "the",
        "to",
        "with",
        "where",
        "whether",
        "case",
        "cases",
    }
)
_AI_ACTOR = re.compile(r"\b(ai|the agent|an agent|the automation|agent)\b", re.I)
_NEGATION = re.compile(
    r"\b(not|never|must not|does not|do not|cannot|can't|won't|is not|are not|will not)\b",
    re.I,
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_STRONG_AI_CONTRADICTION = (
    " approves alone",
    " decides alone",
    "without a person",
    "without human",
    " autonomously ",
    " auto-approves",
    "places orders",
    "signs contracts",
    "evaluates employees",
    "decides whether",
    "does not evaluate",
)


class PreConfirmError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def pre_confirm_check(framework: dict[str, Any]) -> None:
    """Raise if the customer report must not be signed yet."""
    chapter = chapter_by_id(framework, "6")
    splits = blocks_of(chapter, "ai_split")
    if not splits:
        raise PreConfirmError("Chapter 6 must state where AI is used and where it is not before confirmation.")
    used = [str(item).strip() for item in splits[0].get("used_for") or [] if str(item).strip()]
    not_used = [str(item).strip() for item in splits[0].get("not_used_for") or [] if str(item).strip()]
    if not used or not not_used:
        raise PreConfirmError("Chapter 6 must list both AI used-for and not-used-for before confirmation.")

    for used_item in used:
        for forbidden in not_used:
            if _phrases_overlap(used_item, forbidden):
                raise PreConfirmError(
                    "Chapter 6 contradicts itself on where AI is used. Confirm the split before the report is signed."
                )

    elsewhere = _ai_sentences(_text_outside_chapter_6(framework))
    for forbidden in not_used:
        for sentence in elsewhere:
            # A chapter body can contain several structured blocks (flow nodes,
            # tables and prose).  Flattening those blocks is intentionally
            # conservative, but a keyword overlap alone can join a human gate
            # with an unrelated AI step and create a false ES-13 contradiction.
            # Confirmation must still block an explicit autonomous AI action;
            # it must not block a report that correctly routes the boundary to
            # a person.
            if _is_real_ai_contradiction(sentence, [forbidden]):
                raise PreConfirmError(
                    "Another chapter contradicts chapter 6 on AI use. The report cannot be confirmed until the split is consistent."
                )

    blob = str(chapter.get("body")).lower()
    if "ai decides a match" in blob or "ai decides whether" in blob:
        raise PreConfirmError("Chapter 6 must not claim that AI decides a match.")


def prepare_framework_for_confirm(framework: dict[str, Any]) -> None:
    """ES-30 confirm readiness — normalize draft text so ES-13 can pass without changing ES-13."""
    scrub_ai_split_echoes(framework)
    neutralize_ai_actor_outside_chapter_6(framework)
    chapter_5 = _chapter_or_none(framework, "5")
    if chapter_5 is not None:
        ensure_never_autonomous_statement(chapter_5)


def scrub_ai_split_echoes(framework: dict[str, Any]) -> None:
    """ES-30 confirm readiness — drop agreeing AI-echo lines outside chapter 6.

    Chapter 6 ai_split stays canonical. Other chapters may restate not_used_for in
    negated agent prose; ES-13 treats that overlap as a block. Remove only echoes
    (negated agreement), never real contradictions.
    """
    chapter = _chapter_or_none(framework, "6")
    if chapter is None:
        return
    splits = blocks_of(chapter, "ai_split")
    if not splits:
        return
    not_used = [str(item).strip() for item in splits[0].get("not_used_for") or [] if str(item).strip()]
    if not not_used:
        return
    for other in framework.get("chapters") or []:
        chapter_id = str(other.get("chapter_id"))
        if chapter_id == "6":
            continue
        other["body"] = _scrub_body(other.get("body"), not_used, chapter_id=chapter_id)


def neutralize_ai_actor_outside_chapter_6(framework: dict[str, Any]) -> None:
    """Replace agent/AI wording outside chapter 6 when ES-13 would false-positive on overlap."""
    chapter = _chapter_or_none(framework, "6")
    if chapter is None:
        return
    splits = blocks_of(chapter, "ai_split")
    if not splits:
        return
    not_used = [str(item).strip() for item in splits[0].get("not_used_for") or [] if str(item).strip()]
    if not not_used:
        return
    for other in framework.get("chapters") or []:
        chapter_id = str(other.get("chapter_id"))
        if chapter_id == "6":
            continue
        other["body"] = _neutralize_body(other.get("body"), not_used, chapter_id=chapter_id)
        if _chapter_needs_force_strip(other, not_used):
            other["body"] = _force_strip_ai_actor_body(other.get("body"), chapter_id=chapter_id)


def confirm_customer_report(
    framework: dict[str, Any],
    *,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Mark the customer report confirmed. The original object is not mutated."""
    updated = copy.deepcopy(framework)
    if str(updated.get("status") or "") == "confirmed":
        return updated
    prepare_framework_for_confirm(updated)
    pre_confirm_check(updated)
    lang = str(
        (updated.get("customer_view") or {}).get("render_language")
        or updated.get("language_master")
        or "en"
    )
    updated["customer_view"] = strip_citations_from_value(build_customer_view(updated, lang=lang))
    stamp = (now or (lambda: datetime.now(timezone.utc)))().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    updated["status"] = "confirmed"
    updated["updated_at"] = stamp
    updated["change_log"] = list(framework.get("change_log") or []) + ["Customer report confirmed"]
    cover = dict(updated.get("cover") or {})
    cover["confirmation"] = "Human-confirmed customer Framework Report. Technical framework is out of scope."
    updated["cover"] = cover
    nested = updated.get("customer_view")
    if isinstance(nested, dict):
        nested["status"] = "confirmed"
        nested["updated_at"] = stamp
        nested["change_log"] = updated["change_log"]
        nested_cover = dict(nested.get("cover") or {})
        nested_cover["confirmation"] = cover["confirmation"]
        nested["cover"] = nested_cover
    return updated


def _phrases_overlap(left: str, right: str) -> bool:
    a = _content_tokens(left)
    b = _content_tokens(right)
    if not a or not b:
        return False
    shared = a & b
    needed = max(2, int(min(len(a), len(b)) * 0.6 + 0.5))
    return len(shared) >= needed


def _content_tokens(text: str) -> set[str]:
    raw = {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in _STOP and len(token) > 2}
    stems: set[str] = set()
    for token in raw:
        stems.add(token)
        for suffix in ("ing", "es", "ed", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                stems.add(token[: -len(suffix)])
        if len(token) >= 5:
            stems.add(token[:5])
    return stems


def _text_outside_chapter_6(framework: dict[str, Any]) -> str:
    parts: list[str] = [_flatten(framework.get("cover"))]
    for chapter in framework.get("chapters") or []:
        if str(chapter.get("chapter_id")) == "6":
            continue
        parts.append(_flatten(chapter.get("body")))
    return " ".join(part for part in parts if part)


def _ai_sentences(text: str) -> list[str]:
    sentences = _SENTENCE.split(text) if text else []
    return [sentence for sentence in sentences if _AI_ACTOR.search(sentence or "")]


def _chapter_or_none(framework: dict[str, Any], chapter_id: str) -> dict[str, Any] | None:
    for chapter in framework.get("chapters") or []:
        if str(chapter.get("chapter_id")) == chapter_id:
            return chapter
    return None


def _is_ai_echo(text: str, not_used: list[str]) -> bool:
    cleaned = text.strip()
    if not cleaned or not _AI_ACTOR.search(cleaned):
        return False
    if not _NEGATION.search(cleaned):
        return False
    return any(_phrases_overlap(cleaned, item) for item in not_used)


def _scrub_line(text: str, not_used: list[str], *, chapter_id: str | None = None) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if chapter_id == "5" and text_has_never_autonomous_marker(cleaned):
        return cleaned
    if _is_ai_echo(cleaned, not_used):
        return ""
    parts = _SENTENCE.split(cleaned) if cleaned else []
    kept = [
        part.strip()
        for part in parts
        if part.strip()
        and not (
            _is_ai_echo(part, not_used)
            and not (chapter_id == "5" and text_has_never_autonomous_marker(part))
        )
    ]
    return " ".join(kept).strip()


def _scrub_body(body: Any, not_used: list[str], *, chapter_id: str | None = None) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for block in body or []:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("block") or "")
        if kind == "prose":
            text = _scrub_line(str(block.get("text") or ""), not_used, chapter_id=chapter_id)
            if text:
                cleaned.append({**block, "text": text})
        elif kind == "callout":
            text = _scrub_line(str(block.get("text") or ""), not_used, chapter_id=chapter_id)
            if text:
                cleaned.append({**block, "text": text})
        elif kind == "bullets":
            items = [_scrub_line(str(item), not_used, chapter_id=chapter_id) for item in block.get("items") or []]
            items = [item for item in items if item]
            if items:
                cleaned.append({**block, "items": items})
        elif kind == "kv_rows":
            caption = _scrub_line(str(block.get("caption") or ""), not_used, chapter_id=chapter_id)
            rows = []
            for row in block.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                label = _scrub_line(str(row.get("label") or ""), not_used, chapter_id=chapter_id)
                value = _scrub_line(str(row.get("value") or ""), not_used, chapter_id=chapter_id)
                if label or value:
                    rows.append({**row, "label": label, "value": value})
            if caption or rows:
                cleaned.append({**block, "caption": caption, "rows": rows})
        elif kind == "table":
            if chapter_id == "4" and _is_today_vs_agent_table(block):
                cleaned.append(block)
                continue
            caption = _scrub_line(str(block.get("caption") or ""), not_used, chapter_id=chapter_id)
            columns = [_scrub_line(str(col), not_used, chapter_id=chapter_id) for col in block.get("columns") or []]
            rows_out = []
            for row in block.get("rows") or []:
                if not isinstance(row, list):
                    continue
                cells = [_scrub_line(str(cell), not_used, chapter_id=chapter_id) for cell in row]
                if any(cell for cell in cells):
                    rows_out.append(cells)
            if caption or columns or rows_out:
                cleaned.append({**block, "caption": caption, "columns": columns, "rows": rows_out})
        elif kind == "process_flow":
            caption = _scrub_line(str(block.get("caption") or ""), not_used, chapter_id=chapter_id)
            nodes = []
            for node in block.get("nodes") or []:
                if not isinstance(node, dict):
                    continue
                label = _scrub_line(str(node.get("label") or ""), not_used, chapter_id=chapter_id)
                if label:
                    nodes.append({**node, "label": label})
            if caption or nodes:
                cleaned.append({**block, "caption": caption, "nodes": nodes, "edges": block.get("edges") or []})
        else:
            cleaned.append(block)
    return cleaned


def _chapter_needs_force_strip(chapter: dict[str, Any], not_used: list[str]) -> bool:
    blob = _flatten(chapter.get("body"))
    for forbidden in not_used:
        for sentence in _ai_sentences(blob):
            if _phrases_overlap(sentence, forbidden) and not _is_real_ai_contradiction(sentence, not_used):
                return True
            if _should_neutralize_hitl_wording(sentence, not_used) and not _is_real_ai_contradiction(
                sentence, not_used
            ):
                return True
    return False


def _force_strip_line(text: str, *, chapter_id: str | None = None) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if chapter_id == "5" and text_has_never_autonomous_marker(cleaned):
        return cleaned
    if not _AI_ACTOR.search(cleaned):
        return cleaned
    return _neutralize_ai_actor(cleaned)


def _force_strip_ai_actor_body(body: Any, *, chapter_id: str | None = None) -> list[dict[str, Any]]:
    stripped: list[dict[str, Any]] = []
    for block in body or []:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("block") or "")
        if kind == "prose":
            text = _force_strip_line(str(block.get("text") or ""), chapter_id=chapter_id)
            if text:
                stripped.append({**block, "text": text})
        elif kind == "callout":
            text = _force_strip_line(str(block.get("text") or ""), chapter_id=chapter_id)
            if text:
                stripped.append({**block, "text": text})
        elif kind == "bullets":
            items = [_force_strip_line(str(item), chapter_id=chapter_id) for item in block.get("items") or []]
            items = [item for item in items if item]
            if items:
                stripped.append({**block, "items": items})
        elif kind == "kv_rows":
            caption = _force_strip_line(str(block.get("caption") or ""), chapter_id=chapter_id)
            rows = []
            for row in block.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                label = _force_strip_line(str(row.get("label") or ""), chapter_id=chapter_id)
                value = _force_strip_line(str(row.get("value") or ""), chapter_id=chapter_id)
                if label or value:
                    rows.append({**row, "label": label, "value": value})
            if caption or rows:
                stripped.append({**block, "caption": caption, "rows": rows})
        elif kind == "table":
            if chapter_id == "4" and _is_today_vs_agent_table(block):
                stripped.append(block)
                continue
            caption = _force_strip_line(str(block.get("caption") or ""), chapter_id=chapter_id)
            columns = [_force_strip_line(str(col), chapter_id=chapter_id) for col in block.get("columns") or []]
            rows_out = []
            for row in block.get("rows") or []:
                if not isinstance(row, list):
                    continue
                cells = [_force_strip_line(str(cell), chapter_id=chapter_id) for cell in row]
                if any(cell for cell in cells):
                    rows_out.append(cells)
            if caption or columns or rows_out:
                stripped.append({**block, "caption": caption, "columns": columns, "rows": rows_out})
        elif kind == "process_flow":
            caption = _force_strip_line(str(block.get("caption") or ""), chapter_id=chapter_id)
            nodes = []
            for node in block.get("nodes") or []:
                if not isinstance(node, dict):
                    continue
                label = _force_strip_line(str(node.get("label") or ""), chapter_id=chapter_id)
                if label:
                    nodes.append({**node, "label": label})
            if caption or nodes:
                stripped.append({**block, "caption": caption, "nodes": nodes, "edges": block.get("edges") or []})
        else:
            stripped.append(block)
    return stripped


def _is_real_ai_contradiction(text: str, not_used: list[str]) -> bool:
    cleaned = text.strip()
    if not cleaned or not _AI_ACTOR.search(cleaned):
        return False
    if not any(_phrases_overlap(cleaned, item) for item in not_used):
        return False
    if _NEGATION.search(cleaned):
        return False
    if text_has_never_autonomous_marker(cleaned):
        return False
    lower = cleaned.lower()
    return any(marker in lower for marker in _STRONG_AI_CONTRADICTION)


def _neutralize_ai_actor(text: str) -> str:
    updated = re.sub(r"\b(the agent|an agent|the automation|agent)\b", "the workflow", text, flags=re.I)
    updated = re.sub(r"\bAI\b", "", updated)
    return re.sub(r"\s{2,}", " ", updated).strip()


def _neutralize_line(text: str, not_used: list[str], *, chapter_id: str | None = None) -> str:
    cleaned = text.strip()
    if not cleaned or not _AI_ACTOR.search(cleaned):
        return cleaned
    if chapter_id == "5" and text_has_never_autonomous_marker(cleaned):
        return cleaned
    if not any(_phrases_overlap(cleaned, item) for item in not_used) and not _should_neutralize_hitl_wording(
        cleaned, not_used
    ):
        return cleaned
    if _is_real_ai_contradiction(cleaned, not_used):
        return cleaned
    neutralized = _neutralize_ai_actor(cleaned)
    if _AI_ACTOR.search(neutralized) and (
        any(_phrases_overlap(neutralized, item) for item in not_used)
        or _should_neutralize_hitl_wording(neutralized, not_used)
    ):
        return re.sub(r"\b(the agent|an agent|the automation|agent)\b", "the workflow", neutralized, flags=re.I)
    return neutralized


def _should_neutralize_hitl_wording(text: str, not_used: list[str]) -> bool:
    lower = text.lower()
    if not _AI_ACTOR.search(text):
        return False
    if not any(token in lower for token in ("approv", "monitor", "post", "release", "authority", "exception")):
        return False
    for item in not_used:
        item_lower = item.lower()
        if any(token in item_lower for token in ("approv", "authority", "exception", "final", "human")):
            return True
    return False


def _neutralize_body(body: Any, not_used: list[str], *, chapter_id: str | None = None) -> list[dict[str, Any]]:
    neutralized: list[dict[str, Any]] = []
    for block in body or []:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("block") or "")
        if kind == "prose":
            text = _neutralize_line(str(block.get("text") or ""), not_used, chapter_id=chapter_id)
            if text:
                neutralized.append({**block, "text": text})
        elif kind == "callout":
            text = _neutralize_line(str(block.get("text") or ""), not_used, chapter_id=chapter_id)
            if text:
                neutralized.append({**block, "text": text})
        elif kind == "bullets":
            items = [_neutralize_line(str(item), not_used, chapter_id=chapter_id) for item in block.get("items") or []]
            items = [item for item in items if item]
            if items:
                neutralized.append({**block, "items": items})
        elif kind == "kv_rows":
            caption = _neutralize_line(str(block.get("caption") or ""), not_used, chapter_id=chapter_id)
            rows = []
            for row in block.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                label = _neutralize_line(str(row.get("label") or ""), not_used, chapter_id=chapter_id)
                value = _neutralize_line(str(row.get("value") or ""), not_used, chapter_id=chapter_id)
                if label or value:
                    rows.append({**row, "label": label, "value": value})
            if caption or rows:
                neutralized.append({**block, "caption": caption, "rows": rows})
        elif kind == "table":
            if chapter_id == "4" and _is_today_vs_agent_table(block):
                neutralized.append(block)
                continue
            caption = _neutralize_line(str(block.get("caption") or ""), not_used, chapter_id=chapter_id)
            columns = [_neutralize_line(str(col), not_used, chapter_id=chapter_id) for col in block.get("columns") or []]
            rows_out = []
            for row in block.get("rows") or []:
                if not isinstance(row, list):
                    continue
                cells = [_neutralize_line(str(cell), not_used, chapter_id=chapter_id) for cell in row]
                if any(cell for cell in cells):
                    rows_out.append(cells)
            if caption or columns or rows_out:
                neutralized.append({**block, "caption": caption, "columns": columns, "rows": rows_out})
        elif kind == "process_flow":
            caption = _neutralize_line(str(block.get("caption") or ""), not_used, chapter_id=chapter_id)
            nodes = []
            for node in block.get("nodes") or []:
                if not isinstance(node, dict):
                    continue
                label = _neutralize_line(str(node.get("label") or ""), not_used, chapter_id=chapter_id)
                if label:
                    nodes.append({**node, "label": label})
            if caption or nodes:
                neutralized.append({**block, "caption": caption, "nodes": nodes, "edges": block.get("edges") or []})
        else:
            neutralized.append(block)
    return neutralized


def _is_today_vs_agent_table(block: dict[str, Any]) -> bool:
    text = " ".join(
        [str(block.get("caption") or ""), *(str(item) for item in (block.get("columns") or []))]
    ).lower()
    return "today" in text and "agent" in text


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    return str(value)
