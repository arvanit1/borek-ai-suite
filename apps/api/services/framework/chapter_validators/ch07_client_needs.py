"""ES-21 — chapter 7 client needs acceptance."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    tables = blocks_of(chapter, "table")
    if not tables:
        issues.append(ChapterIssue("7", "prerequisites", "Chapter 7 must list what is needed from the client."))
    else:
        table_blob = str(tables).lower()
        if "status" not in table_blob or "owner" not in table_blob:
            issues.append(
                ChapterIssue("7", "status_owner", "Chapter 7 access/readiness table must include status and owner.")
            )
        if "hour" not in table_blob:
            issues.append(
                ChapterIssue("7", "hours", "Chapter 7 access/readiness table must include hours.")
            )
    for index, need in enumerate(framework.get("access_needs") or []):
        if not need.get("status") or not need.get("owner"):
            issues.append(ChapterIssue("7", "status_owner", f"Prerequisite {index} is missing status or owner."))
    categories = " ".join(str(item.get("category", "")).lower() for item in framework.get("access_needs") or [])
    for token in ("read", "write", "sample", "identity", "rule"):
        if token not in categories:
            issues.append(
                ChapterIssue(
                    "7",
                    "access_categories",
                    "Chapter 7 must cover read, write, test/sample data, rule confirmation, and identity categories.",
                )
            )
            break
    return issues
