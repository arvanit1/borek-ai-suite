"""ES-24 — chapter 10 complexity, effort & timeline."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    blob = chapter_blob(chapter)
    estimate = framework.get("estimate") or {}
    weeks = estimate.get("effort_weeks") or {}
    if not {"min", "likely", "max"} <= set(weeks):
        issues.append(ChapterIssue("10", "range", "Chapter 10 must show min / likely / max weeks, never a single point."))
    if not estimate.get("tier") and "tier" not in blob:
        issues.append(ChapterIssue("10", "tier", "Chapter 10 must include a complexity tier."))
    if "confidence" not in blob:
        issues.append(ChapterIssue("10", "confidence", "Chapter 10 must include confidence with the effort range."))
    if "team" not in blob and not (estimate.get("team") or []):
        issues.append(ChapterIssue("10", "team", "Chapter 10 must name the team."))
    if "driver" not in blob and "assumption" not in blob:
        issues.append(ChapterIssue("10", "drivers", "Chapter 10 must include the effort drivers."))
    if not blocks_of(chapter, "timeline"):
        issues.append(ChapterIssue("10", "timeline", "Chapter 10 must include a week plan."))
    if "chapter 12" not in blob and "ch.12" not in blob:
        issues.append(
            ChapterIssue("10", "aligned_ch12", "Chapter 10 week plan must be aligned to the recommended stage in chapter 12.")
        )
    return issues
