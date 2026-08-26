"""ES-17 — chapter 3 Aim & success measurement acceptance."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    blob = chapter_blob(chapter)
    if "conservative" not in blob:
        issues.append(
            ChapterIssue(
                "3",
                "conservative",
                "Chapter 3 KPIs must be a conservative derivation from the conversations.",
            )
        )
    tables = blocks_of(chapter, "table")
    table_blob = str(tables).lower()
    if not tables or "baseline" not in table_blob or "target" not in table_blob or (
        "measured" not in table_blob and "method" not in table_blob
    ):
        issues.append(
            ChapterIssue("3", "kpi_table", "Chapter 3 must include a KPI table with baseline, target, measured_via.")
        )
    for index, kpi in enumerate(framework.get("kpis") or []):
        if not kpi.get("baseline") or not kpi.get("target") or not kpi.get("measured_via"):
            issues.append(
                ChapterIssue("3", "kpi_fields", f"KPI {index} is missing baseline, target, or measured_via.")
            )
    kpi_names = " ".join(str(item.get("name", "")).lower() for item in framework.get("kpis") or [])
    for token, label in (
        (("automation", "auto-match", "auto match"), "automation rate"),
        (("manual", "handling time", "hours"), "manual time"),
        (("quality", "error", "wrong", "success"), "quality/error"),
        (("cycle", "lead time", "close", "month-end"), "cycle time"),
    ):
        if not any(part in kpi_names for part in token):
            issues.append(
                ChapterIssue(
                    "3",
                    "kpi_categories",
                    f"Chapter 3 must include a KPI for {label}.",
                )
            )
    return issues
