"""ES-28 — attach source_refs per factual block using knowledge-entry overlap."""

from __future__ import annotations

import re
from typing import Any

from services.framework.chapter_validators.base import ChapterIssue

_FACTUAL_BLOCKS = frozenset(
    {
        "prose",
        "bullets",
        "kv_rows",
        "table",
        "process_flow",
        "callout",
        "ai_split",
        "sensitivity",
        "timeline",
        "score_bars",
        "glossary",
    }
)
_STOP = frozenset({"the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "has", "have"})


def attach_block_source_refs(
    framework: dict[str, Any],
    knowledge_entries: list[dict[str, Any]] | None = None,
) -> None:
    """Map each factual block to the best matching knowledge entry refs (ES-28)."""
    entries = knowledge_entries or []
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        body = chapter.get("body")
        if not isinstance(body, list):
            continue
        updated: list[dict[str, Any]] = []
        for block in body:
            if not isinstance(block, dict):
                continue
            if str(block.get("block") or "") not in _FACTUAL_BLOCKS or not _block_has_text(block):
                updated.append(block)
                continue
            if block.get("source_refs"):
                updated.append(block)
                continue
            text = _block_text(block)
            minimum_overlap = _minimum_overlap(block)
            matched = _refs_for_text(text, entries, minimum_overlap=minimum_overlap)
            if matched and _refs_support_text(text, matched, entries, minimum_overlap=minimum_overlap):
                updated.append({**block, "source_refs": matched})
            else:
                updated.append(block)
        chapter["body"] = updated


def collect_block_traceability_issues(
    framework: dict[str, Any],
    knowledge_entries: list[dict[str, Any]] | None = None,
) -> list[ChapterIssue]:
    entries = knowledge_entries or []
    issues: list[ChapterIssue] = []
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id"))
        for index, block in enumerate(chapter.get("body") or []):
            if not isinstance(block, dict):
                continue
            if not _block_requires_traceability(block):
                continue
            if str(block.get("tone") or "") == "open_item":
                continue
            refs = block.get("source_refs") or []
            if not refs:
                issues.append(
                    ChapterIssue(
                        chapter_id,
                        "block_source_refs",
                        f"Factual block {index} in chapter {chapter_id} must carry source_refs (ES-28).",
                    )
                )
                continue
            if entries and not _refs_support_text(
                _block_text(block),
                refs,
                entries,
                minimum_overlap=_minimum_overlap(block),
            ):
                issues.append(
                    ChapterIssue(
                        chapter_id,
                        "block_source_mismatch",
                        f"Factual block {index} in chapter {chapter_id} lacks a matching knowledge entry (ES-28).",
                    )
                )
    return issues


def convert_unsupported_block_claims(
    framework: dict[str, Any],
    knowledge_entries: list[dict[str, Any]] | None = None,
) -> None:
    """ES-28 — claims whose source_refs do not support the text become open items."""
    from services.framework.guardrails import _refresh_open_items_table

    entries = knowledge_entries or []
    for chapter in framework.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id"))
        body = chapter.get("body")
        if not isinstance(body, list):
            continue
        updated: list[dict[str, Any]] = []
        for block in body:
            if not isinstance(block, dict):
                updated.append(block)
                continue
            if not _block_requires_traceability(block):
                updated.append(block)
                continue
            if str(block.get("tone") or "") == "open_item":
                updated.append(block)
                continue
            claim = _block_text(block)
            refs = block.get("source_refs") or []
            if not refs:
                reason = "it has no cited conversation excerpt"
            elif _refs_support_text(claim, refs, entries, minimum_overlap=_minimum_overlap(block)):
                updated.append(block)
                continue
            else:
                reason = "its cited source does not support the text"
            framework.setdefault("open_items", []).append(
                {
                    "description": (
                        f"Claim in chapter {chapter_id} is not supported because {reason}: "
                        f"{claim[:240]}. Recorded as an open item rather than accepted."
                    ),
                    "item_type": "assumption",
                    "owner": "Business",
                    "consequence_if_different": (
                        "Unsupported claims are never published. Confirm the statement against the conversation."
                    ),
                }
            )
            updated.append(
                {
                    "block": "callout",
                    "tone": "open_item",
                    "text": (
                        "This point is recorded as an open item because it is not supported "
                        "by a conversation excerpt."
                    ),
                }
            )
        chapter["body"] = updated
    _refresh_open_items_table(framework)


def _refs_for_text(
    text: str,
    entries: list[dict[str, Any]],
    *,
    minimum_overlap: int = 2,
) -> list[dict[str, str]]:
    if not text.strip() or not entries:
        return []
    best_score = 0
    best_refs: list[dict[str, str]] = []
    block_tokens = _tokens(text)
    if not block_tokens:
        return []
    for entry in entries:
        statement = str(entry.get("statement") or "")
        if not statement.strip():
            continue
        entry_tokens = _tokens(statement)
        if not entry_tokens:
            continue
        shared = block_tokens & entry_tokens
        score = len(shared)
        if score > best_score:
            best_score = score
            best_refs = _coerce_refs(entry.get("source_refs") or [])
    return best_refs if best_score >= minimum_overlap else []


def _refs_support_text(
    text: str,
    refs: list[dict[str, str]],
    entries: list[dict[str, Any]],
    *,
    minimum_overlap: int = 2,
) -> bool:
    if not refs:
        return False
    pointers = {
        (str(ref.get("conversation_id")), str(ref.get("excerpt_pointer")))
        for ref in refs
    }
    block_tokens = _tokens(text)
    if not block_tokens:
        return True
    for entry in entries:
        entry_refs = entry.get("source_refs") or []
        if not any(
            (str(ref.get("conversation_id")), str(ref.get("excerpt_pointer"))) in pointers
            for ref in entry_refs
            if isinstance(ref, dict)
        ):
            continue
        if len(block_tokens & _tokens(str(entry.get("statement") or ""))) >= minimum_overlap:
            return True
    return False


def _coerce_refs(refs: list[Any]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        cleaned.append(
            {
                "conversation_id": str(ref.get("conversation_id") or ""),
                "speaker_role": str(ref.get("speaker_role") or ""),
                "excerpt_pointer": str(ref.get("excerpt_pointer") or ""),
            }
        )
    return [ref for ref in cleaned if ref["conversation_id"] and ref["excerpt_pointer"]]


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[\w\u00C0-\u024F]+", text.lower(), flags=re.UNICODE)
    return {token for token in raw if len(token) > 2 and token not in _STOP}


def _block_text(block: dict[str, Any]) -> str:
    kind = str(block.get("block") or "")
    if kind in {"prose", "callout"}:
        return str(block.get("text") or "")
    if kind == "bullets":
        return " ".join(str(item) for item in block.get("items") or [])
    if kind == "kv_rows":
        return " ".join(
            f"{row.get('label', '')} {row.get('value', '')}"
            for row in block.get("rows") or []
            if isinstance(row, dict)
        )
    if kind == "table":
        parts = [str(col) for col in block.get("columns") or []]
        for row in block.get("rows") or []:
            if isinstance(row, list):
                parts.extend(str(cell) for cell in row)
        return " ".join(parts)
    if kind == "process_flow":
        return " ".join(str(node.get("label") or "") for node in block.get("nodes") or [] if isinstance(node, dict))
    if kind == "ai_split":
        return " ".join(
            str(item)
            for field in ("used_for", "not_used_for")
            for item in block.get(field) or []
        )
    if kind == "sensitivity":
        return " ".join(
            f"{row.get('label', '')} {row.get('detail', '')}"
            for row in block.get("rows") or []
            if isinstance(row, dict)
        )
    if kind == "timeline":
        return " ".join(
            f"{week.get('id', '')} {' '.join(str(item) for item in (week.get('items') or []))}"
            for week in block.get("weeks") or []
            if isinstance(week, dict)
        )
    if kind == "score_bars":
        return " ".join(
            f"{item.get('name', '')} {item.get('score', '')} {item.get('explanation', '')}"
            for item in block.get("items") or []
            if isinstance(item, dict)
        )
    if kind == "glossary":
        return " ".join(
            f"{item.get('term', '')} {item.get('meaning', '')}"
            for item in block.get("terms") or []
            if isinstance(item, dict)
        )
    return ""


def _block_has_text(block: dict[str, Any]) -> bool:
    return bool(_block_text(block).strip())


def _minimum_overlap(block: dict[str, Any]) -> int:
    """Structured derivations can cite the source item named by a single step label."""
    if str(block.get("block") or "") in {"kv_rows", "table", "process_flow", "sensitivity", "timeline", "score_bars", "glossary", "ai_split"}:
        return 1
    return 2


def _block_requires_traceability(block: dict[str, Any]) -> bool:
    """Only customer-facing assertions need a conversation citation.

    Chapter scaffolding such as a caption or a neutral delivery label is not a
    source claim.  Every structured block and every declarative prose/callout/
    bullet block is fail-closed, however.
    """
    if str(block.get("block") or "") not in _FACTUAL_BLOCKS or not _block_has_text(block):
        return False
    text = _block_text(block).lower()
    # Typed chapter scaffolding and neutral safety wording are framework
    # structure, not claims introduced from a customer conversation.
    if "open item" in str(block.get("caption") or "").lower():
        return False
    if str(block.get("kind") or "").lower() == "recommendation":
        return False
    if "next step" in str(block.get("caption") or "").lower():
        return False
    claim_text = _claim_text(block).lower()
    has_number = bool(re.search(r"\b\d[\d,]*(?:\.\d+)?\b", claim_text))
    # ES-28 covers unnumbered rules as well as numbers. Typed key-value
    # blocks and process-flow labels are required report structure; an
    # unnumbered table is a customer claim only when it expresses a rule.
    kind = str(block.get("block") or "")
    if kind in {"kv_rows", "process_flow"}:
        return has_number
    if kind == "table":
        return has_number or _has_unnumbered_table_rule(claim_text)
    # Chapter navigation is report scaffolding; its chapter numbers are not
    # customer facts and must not turn the eight-question list into an open item.
    if str(block.get("block") or "") == "bullets" and "what is it?" in text and "can we trust" in text:
        return False
    if "team decides" in text or "on its own" in text or "from the conversations" in text:
        return False
    if any(
        marker in text
        for marker in (
            "recorded as an open item",
            "never guessed",
            "open items in chapter",
            "open item with an owner",
            "stage-3",
            "stage 3",
            "proposals only",
            "committed business case",
            "human-confirmed before it is the signed",
            "before anything is built, every automation must pass",
            "every automation is designed as a path",
            "formulas disclosed, assumptions marked",
            "qualitative benefits were not priced in",
            "empty cells are open items",
            # Ch.0 / Ch.7 framework boilerplate — not customer conversation claims.
            "every number in this report is traceable",
            "estimates are shown as ranges",
            "never as false precision",
            "false-precision figures",
            "borek ai suite generates exactly one",
            "table below lists access",
            "access, data, and readiness items we need from you",
            "hours are named in the conversations or listed as an open item",
        )
    ):
        return False
    return has_number or _has_rule_or_claim_marker(text)


def _has_rule_or_claim_marker(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:must|should|cannot|never|always|only|autonomously|automatic(?:ally)?|"
            r"manual(?:ly)?|approve(?:s|d|ing)?|select(?:s|ed|ing)?|match(?:es|ed|ing)?|"
            r"process(?:es|ed|ing)?|receive(?:s|d|ing)?|send(?:s|ing)?|"
            r"arrive(?:s|d|ing)?|require(?:s|d|ing)?|rule|exception|route(?:s|d|ing)?|"
            r"hold(?:s|ing)?|reject(?:s|ed|ing)?|release(?:s|d|ing)?)\b",
            text,
        )
    )


def _has_unnumbered_table_rule(text: str) -> bool:
    return bool(
        "→" in text
        or re.search(
            r"\b(?:if|then|automatically|autonomously|route(?:s|d|ing)?|"
            r"hold(?:s|ing)?|reject(?:s|ed|ing)?|release(?:s|d|ing)?)\b",
            text,
        )
    )


def _claim_text(block: dict[str, Any]) -> str:
    """Return customer assertions without neutral table headers/captions."""
    kind = str(block.get("block") or "")
    if kind == "table":
        return " ".join(
            str(cell)
            for row in block.get("rows") or []
            if isinstance(row, list)
            for cell in row
        )
    if kind == "kv_rows":
        return " ".join(
            str(row.get("value") or "")
            for row in block.get("rows") or []
            if isinstance(row, dict)
        )
    return _block_text(block)
