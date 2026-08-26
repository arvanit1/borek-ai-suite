"""ES-23 — chapter 9 business case & ROI."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    business = framework.get("business_case") or {}
    if not business:
        issues.append(ChapterIssue("9", "engine", "Chapter 9 requires a computed business_case on the model."))
    if not blocks_of(chapter, "table"):
        issues.append(
            ChapterIssue(
                "9",
                "calc_table",
                "Chapter 9 must include the calculation table structure even when currency is missing.",
            )
        )
    if not blocks_of(chapter, "bullets") and "qualitative" not in chapter_blob(chapter):
        issues.append(ChapterIssue("9", "qualitative", "Chapter 9 must include qualitative benefits."))
    sensitivities = blocks_of(chapter, "sensitivity")
    rows = [row for block in sensitivities for row in (block.get("rows") or [])]
    if len(rows) < 3:
        issues.append(ChapterIssue("9", "sensitivity", "Chapter 9 must include a three-point sensitivity block."))
    if "payback" not in chapter_blob(chapter):
        issues.append(
            ChapterIssue("9", "payback", "Chapter 9 must include the payback row in the calculation table.")
        )
    blob = chapter_blob(chapter)
    if "effort today" not in blob and "automatable" not in blob:
        issues.append(ChapterIssue("9", "effort_today", "Chapter 9 calculation table must include effort today."))
    if "automation rate" not in blob and "auto-match" not in blob:
        issues.append(ChapterIssue("9", "automation_rate", "Chapter 9 calculation table must include automation rate."))
    if business.get("payback_months") is None and not _payback_is_open_item(framework):
        issues.append(
            ChapterIssue(
                "9",
                "payback",
                "Payback cannot be calculated from the conversations. Record it as an open item; do not guess.",
            )
        )
    return issues


def _payback_is_open_item(framework: dict[str, Any]) -> bool:
    blob = str(framework.get("open_items") or "").lower()
    return "payback" in blob
