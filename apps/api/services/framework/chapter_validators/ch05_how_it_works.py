"""ES-19 — chapter 5 How it works in detail acceptance."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob

_NEVER_AUTO_MARKERS = (
    "on its own",
    "never-autonomous",
    "never autonomous",
    "people decide",
    "team decides",
)
_NEVER_AUTO_CALLOUT = (
    "On exceptions, people decide — the agent is never autonomous toward counterparties."
)


def has_never_autonomous_statement(chapter: dict[str, Any]) -> bool:
    blob = chapter_blob(chapter).lower()
    return text_has_never_autonomous_marker(blob)


def text_has_never_autonomous_marker(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in _NEVER_AUTO_MARKERS)


def ensure_never_autonomous_statement(chapter: dict[str, Any]) -> None:
    """ES-19 — required callout after AI-echo scrubbing must not remove it."""
    if has_never_autonomous_statement(chapter):
        return
    body = list(chapter.get("body") or [])
    body.append(
        {
            "block": "callout",
            "kind": "important",
            "text": _NEVER_AUTO_CALLOUT,
        }
    )
    chapter["body"] = body


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    blob = chapter_blob(chapter)
    glances = blocks_of(chapter, "kv_rows")
    labels = " ".join(
        str(row.get("label", ""))
        for block in glances
        for row in (block.get("rows") or [])
        if isinstance(row, dict)
    ).lower()
    if any(token not in labels for token in ("trigger", "input", "result")):
        issues.append(
            ChapterIssue("5", "trigger_inputs_result", "Chapter 5 must include trigger, inputs, and result.")
        )
    tables = blocks_of(chapter, "table")
    table_blob = str(tables).lower()
    if not (framework.get("rules") or ("rule" in table_blob)):
        issues.append(ChapterIssue("5", "rules", "Chapter 5 must include the confirmed checking rules."))
    if "conversation" not in blob and "transcript" not in blob and "named" not in blob:
        issues.append(
            ChapterIssue("5", "rules_source", "Chapter 5 rules must come from the conversations only.")
        )
    if "exception" not in table_blob and not (framework.get("exceptions") or []):
        issues.append(ChapterIssue("5", "exceptions", "Chapter 5 must list exceptions."))
    if not has_never_autonomous_statement(chapter):
        issues.append(
            ChapterIssue(
                "5",
                "never_autonomous",
                "Chapter 5 must state that the agent is never autonomous on exceptions.",
            )
        )
    return issues
