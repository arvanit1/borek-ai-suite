"""ES-14 — chapter 0 About acceptance."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob

_EIGHT_MARKERS = (
    "what is it",
    "why do it",
    "how does it work",
    "how is it built",
    "what do we need",
    "is it safe",
    "does it pay",
    "can we trust",
)


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    blob = chapter_blob(chapter)
    if "generated" not in blob or (
        "human-confirmed" not in blob and "human confirmed" not in blob
    ):
        issues.append(
            ChapterIssue(
                "0",
                "generated_confirmed",
                "Chapter 0 must say the report is generated and human-confirmed.",
            )
        )
    if "traceable" not in blob and "source" not in blob:
        issues.append(ChapterIssue("0", "traceability", "Chapter 0 must say that every number is traceable."))
    if "range" not in blob and "ranges" not in blob:
        issues.append(ChapterIssue("0", "ranges", "Chapter 0 must say estimates are shown as ranges."))
    if "false precision" not in blob and "false-precision" not in blob:
        issues.append(
            ChapterIssue("0", "false_precision", "Chapter 0 must say estimates are ranges, never false precision.")
        )
    bullets = blocks_of(chapter, "bullets")
    items: list[str] = []
    for block in bullets:
        items.extend(str(item) for item in (block.get("items") or []))
    if len(items) < 8:
        issues.append(
            ChapterIssue("0", "decision_questions", "Chapter 0 must list the eight decision questions the report answers.")
        )
    else:
        joined = " ".join(items).lower()
        missing = [marker for marker in _EIGHT_MARKERS if marker not in joined]
        if missing:
            issues.append(
                ChapterIssue(
                    "0",
                    "decision_questions",
                    "Chapter 0 must list the eight decision questions the report answers.",
                )
            )
    return issues
