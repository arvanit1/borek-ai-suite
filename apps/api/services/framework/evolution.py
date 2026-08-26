"""Evolution ladder: today → assistive → autonomous+HITL → end-to-end proposals."""

from __future__ import annotations

from typing import Any


def generate_evolution(
    *,
    today_description: str,
    stage2_agent_does: str,
    stage2_human_does: str,
    stage2_benefit: str,
    stage2_effort: str,
    stage3_candidates: list[dict[str, str]],
    stage1_value_share: str = "~40 % of time; full visibility",
    stage1_effort: str = "included in base build (interim milestone)",
) -> list[dict[str, Any]]:
    """Stage-3 items without a source reference are dropped, not invented."""
    today = {
        "stage_name": "Today",
        "agent_does": "Nothing — fully manual process.",
        "human_does": today_description or "Everything.",
        "benefit": "—",
        "extra_effort": "—",
        "recommended": False,
    }
    assistive = {
        "stage_name": "Stage 1 · Assistive",
        "agent_does": (
            "Captures, extracts, checks, and prepares complete proposals with reasons. "
            "No write/actuating actions."
        ),
        "human_does": "Confirms every posting or action with one click.",
        "benefit": stage1_value_share,
        "extra_effort": stage1_effort,
        "recommended": False,
    }
    autonomous = {
        "stage_name": "Stage 2 · Autonomous with HITL",
        "agent_does": stage2_agent_does,
        "human_does": stage2_human_does,
        "benefit": stage2_benefit,
        "extra_effort": stage2_effort,
        "recommended": True,
    }

    sourced: list[str] = []
    for candidate in stage3_candidates:
        source = (candidate.get("source_ref") or "").strip()
        if not source:
            continue
        text = (candidate.get("description") or "").strip()
        if text:
            sourced.append(text)

    if sourced:
        stage3_does = (
            "Additionally (proposal only; requires telemetry_3mo and targeted C6 deep-dives): "
            + " · ".join(sourced)
        )
        extra = "~2-3 weeks more, own business case after 3 months of stage-2 data"
        benefit = "Exception effort down; cycle time days to hours. Proposal only — not in the committed business case."
    else:
        stage3_does = (
            "No sourced stage-3 candidates. Nothing is proposed beyond the specified build."
        )
        extra = "—"
        benefit = "—"

    end_to_end = {
        "stage_name": "Stage 3 · End-to-end (option)",
        "agent_does": stage3_does,
        "human_does": "Releases outbound messages; decides on any rule-tuning proposals.",
        "benefit": benefit,
        "extra_effort": extra,
        "recommended": False,
    }
    return [today, assistive, autonomous, end_to_end]
