"""ES-26 — chapter 12 evolution stages."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    blob = chapter_blob(chapter)
    tables = blocks_of(chapter, "table")
    if not tables:
        issues.append(ChapterIssue("12", "ladder", "Chapter 12 must include the evolution stages table."))
    if "today" not in blob:
        issues.append(ChapterIssue("12", "today", "Chapter 12 must include Today."))
    if "assistive" not in blob:
        issues.append(ChapterIssue("12", "stage1", "Chapter 12 must include Stage 1 assistive."))
    if "hitl" not in blob and "human" not in blob:
        issues.append(ChapterIssue("12", "stage2", "Chapter 12 must include Stage 2 with human control (HITL)."))
    if "proposal" not in blob:
        issues.append(ChapterIssue("12", "stage3", "Chapter 12 Stage 3 must be proposal only."))
    stages = framework.get("evolution_stages") or []
    if len(stages) != 4:
        issues.append(ChapterIssue("12", "ladder", "Evolution must have today, stage 1, stage 2, and stage 3."))
        return issues
    recommended = [stage for stage in stages if stage.get("recommended")]
    if len(recommended) != 1:
        issues.append(ChapterIssue("12", "recommended", "Exactly one evolution stage must be recommended (stage 2)."))
    stage3 = stages[-1]
    if "3" not in str(stage3.get("stage_name", "")):
        issues.append(ChapterIssue("12", "stage3", "The last evolution row must be stage 3 / end-to-end."))
    return issues
