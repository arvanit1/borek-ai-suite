"""ES-15 — chapter 1 Management summary acceptance."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    blob = chapter_blob(chapter)
    if not any(block.get("block") == "prose" for block in (chapter.get("body") or []) if isinstance(block, dict)):
        issues.append(ChapterIssue("1", "plain_task", "Chapter 1 must state the task in plain language."))
    glances = blocks_of(chapter, "kv_rows")
    if not glances:
        issues.append(ChapterIssue("1", "glance_table", "Chapter 1 must include an at-a-glance kv_rows block."))
    else:
        labels = " ".join(
            str(row.get("label", ""))
            for block in glances
            for row in (block.get("rows") or [])
            if isinstance(row, dict)
        ).lower()
        if "human" not in labels and "hitl" not in blob:
            issues.append(
                ChapterIssue("1", "hitl", "Chapter 1 at-a-glance must include the human-in-the-loop split.")
            )
        if not any(token in labels or token in blob for token in ("volume", "benefit", "investment", "cost", "eur", "hour")):
            issues.append(
                ChapterIssue("1", "volume_cost", "Chapter 1 must state the task volume and cost in plain language.")
            )
    callouts = blocks_of(chapter, "callout")
    if not callouts:
        issues.append(ChapterIssue("1", "recommendation", "Chapter 1 must include a recommendation callout."))
    else:
        rec = " ".join(str(block.get("text", "")) for block in callouts).lower()
        if "stage" not in rec:
            issues.append(
                ChapterIssue(
                    "1",
                    "recommendation",
                    "Chapter 1 recommendation must name the evolution stage.",
                )
            )
        if "chapter 11" not in rec and "open item" not in rec and "blocking" not in rec:
            issues.append(
                ChapterIssue(
                    "1",
                    "recommendation",
                    "Chapter 1 recommendation must name the blocking open item (chapter 11).",
                )
            )
    return issues
