"""ES-25 — chapter 11 trustworthiness / quality gates."""

from __future__ import annotations

from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of, chapter_blob


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    bars = blocks_of(chapter, "score_bars")
    items = [item for block in bars for item in (block.get("items") or []) if isinstance(item, dict)]
    if len(items) < 3:
        issues.append(ChapterIssue("11", "score_bars", "Chapter 11 must include the three quality-gate score bars."))
    else:
        if any(not str(item.get("explanation") or "").strip() for item in items[:3]):
            issues.append(ChapterIssue("11", "rationale", "Chapter 11 score bars must include a one-line rationale each."))
    scores = framework.get("quality_scores") or {}
    for key in ("opportunity_rating", "conversation_quality", "build_readiness"):
        if key not in scores:
            issues.append(ChapterIssue("11", "score_missing", f"quality_scores.{key} is required."))
        else:
            rationale = str((scores.get("rationale") or {}).get(key) or "").strip()
            if not rationale or "\n" in rationale:
                issues.append(
                    ChapterIssue("11", "rationale", f"Each score must ship a one-line rationale ({key}).")
                )
    if not blocks_of(chapter, "table"):
        issues.append(ChapterIssue("11", "open_items", "Chapter 11 must include the open items table."))
    if "guess" not in chapter_blob(chapter):
        issues.append(
            ChapterIssue("11", "nothing_guessed", "Chapter 11 must state that missing information is never guessed.")
        )
    return issues
