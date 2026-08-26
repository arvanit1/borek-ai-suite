"""ES-22 — chapter 8 security, data protection & human control."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    blob = chapter_blob(chapter)
    if not blocks_of(chapter, "kv_rows"):
        issues.append(ChapterIssue("8", "guardrail", "Chapter 8 must include the binding guardrails list."))
    for token in ("classification", "residency", "audit", "human", "retention"):
        if token not in blob:
            issues.append(
                ChapterIssue("8", "guardrail", f"Chapter 8 must cover {token} as a binding guardrail.")
            )
    if "employee" not in blob:
        issues.append(
            ChapterIssue("8", "employees", "Chapter 8 must state that the agent never evaluates employees.")
        )
    if "breach" not in blob or "acceptance" not in blob:
        issues.append(
            ChapterIssue("8", "breach_at", "Chapter 8 must state that a guardrail breach is a failed acceptance test.")
        )
    if "people" in blob and any(word in blob for word in ("lazy", "slow staff", "unskilled", "incompetent")):
        issues.append(ChapterIssue("8", "tasks_not_people", "Chapter 8 must not evaluate people."))
    return issues
