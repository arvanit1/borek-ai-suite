"""ES-27 — chapter 13 next steps & glossary."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    tables = blocks_of(chapter, "table")
    if not tables:
        issues.append(ChapterIssue("13", "next_steps", "Chapter 13 must include a next-steps table."))
    else:
        table = tables[0]
        columns = " ".join(str(col) for col in (table.get("columns") or [])).lower()
        if "who" not in columns or "when" not in columns:
            issues.append(
                ChapterIssue("13", "who_when", "Chapter 13 next steps must include who and when, or list them as open.")
            )
        for index, row in enumerate(table.get("rows") or []):
            cells = [str(cell).strip() for cell in row] if isinstance(row, list) else []
            if len(cells) >= 4 and (not cells[2] or not cells[3]):
                issues.append(
                    ChapterIssue("13", "who_when", f"Next step {index} is missing who or when; record it as an open item.")
                )
    glossaries = blocks_of(chapter, "glossary")
    terms = [term for block in glossaries for term in (block.get("terms") or [])]
    if not terms:
        issues.append(ChapterIssue("13", "glossary", "Chapter 13 must include a glossary."))
    elif len(terms) < 5:
        issues.append(
            ChapterIssue(
                "13",
                "glossary_coverage",
                "Chapter 13 glossary must define domain-specific terms introduced in the report.",
            )
        )
    return issues
