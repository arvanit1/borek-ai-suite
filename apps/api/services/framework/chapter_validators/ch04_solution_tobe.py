"""ES-18 — chapter 4 to-be process acceptance."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob

_NODE_KINDS = frozenset({"agent", "human", "system", "decision", "start_end"})


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    flows = blocks_of(chapter, "process_flow")
    if not flows:
        issues.append(ChapterIssue("4", "to_be_flow", "Chapter 4 must include the to-be process flow."))
    else:
        nodes = [node for block in flows for node in (block.get("nodes") or []) if isinstance(node, dict)]
        if len(nodes) < 2:
            issues.append(ChapterIssue("4", "to_be_flow", "Chapter 4 must include the to-be process flow."))
        elif any(str(node.get("kind") or "") not in _NODE_KINDS for node in nodes):
            issues.append(
                ChapterIssue(
                    "4",
                    "to_be_flow",
                    "Chapter 4 process steps must use the same typed structure as chapter 2.",
                )
            )
    if "stage" not in chapter_blob(chapter):
        issues.append(
            ChapterIssue("4", "to_be_stage", "Chapter 4 must show the to-be process at the chosen evolution stage.")
        )
    if not _today_vs_agent_table(chapter):
        issues.append(ChapterIssue("4", "today_vs_agent", "Chapter 4 must compare today vs with the agent."))
    return issues


def _today_vs_agent_table(chapter: dict[str, Any]) -> dict[str, Any] | None:
    for table in blocks_of(chapter, "table"):
        if str(table.get("kind") or "") == "today_vs_agent":
            rows = [row for row in (table.get("rows") or []) if isinstance(row, list) and row]
            if len(table.get("columns") or []) >= 2 and rows:
                return table
            continue
        columns = [str(column).lower() for column in (table.get("columns") or [])]
        if (
            len(columns) >= 2
            and any("today" in column or "current" in column for column in columns)
            and any("agent" in column or "to-be" in column or "to be" in column for column in columns)
            and any(isinstance(row, list) and row for row in (table.get("rows") or []))
        ):
            return table
    return None
