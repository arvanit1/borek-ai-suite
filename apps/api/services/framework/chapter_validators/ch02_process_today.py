"""ES-16 — chapter 2 as-is process acceptance."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of

_NODE_KINDS = frozenset({"agent", "human", "system", "decision", "start_end"})


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    flows = blocks_of(chapter, "process_flow")
    if not flows:
        issues.append(
            ChapterIssue("2", "as_is_flow", "Chapter 2 must include typed as-is process steps, not prose only.")
        )
    else:
        nodes = [node for block in flows for node in (block.get("nodes") or []) if isinstance(node, dict)]
        if len(nodes) < 2:
            issues.append(
                ChapterIssue("2", "as_is_flow", "Chapter 2 must include typed as-is process steps, not prose only.")
            )
        elif any(str(node.get("kind") or "") not in _NODE_KINDS for node in nodes):
            issues.append(
                ChapterIssue("2", "as_is_flow", "Chapter 2 process steps must be typed (human, system, agent, decision).")
            )
    if not blocks_of(chapter, "kv_rows"):
        issues.append(ChapterIssue("2", "current_cost", "Chapter 2 must include what the current process costs."))
    else:
        labels = " ".join(
            str(row.get("label", ""))
            for block in blocks_of(chapter, "kv_rows")
            for row in (block.get("rows") or [])
            if isinstance(row, dict)
        ).lower()
        for token in ("clean", "exception", "staff"):
            if token not in labels:
                issues.append(
                    ChapterIssue(
                        "2",
                        "process_handling",
                        "Chapter 2 must include clean vs exception handling time, exception rate, and staff description.",
                    )
                )
                break
    return issues
