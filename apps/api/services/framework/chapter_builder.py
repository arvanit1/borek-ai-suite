"""Deterministic 14-chapter bodies from structured fields. LLM may replace prose; numbers stay engine-owned."""

from __future__ import annotations

import json
import re
from typing import Any

from packages.contracts.validators import chapter_specs_from_registry


def load_chapter_registry() -> list[tuple[str, str]]:
    from pathlib import Path

    path = Path(__file__).resolve().parents[4] / "packages" / "contracts" / "chapter_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    return chapter_specs_from_registry(registry)


def build_chapters(
    *,
    cover: dict[str, Any],
    kpis: list[dict[str, Any]],
    systems: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    exceptions: list[dict[str, Any]],
    access_needs: list[dict[str, Any]],
    open_items: list[dict[str, Any]],
    evolution_stages: list[dict[str, Any]],
    quality_scores: dict[str, Any],
    estimate: dict[str, Any],
    business_case: dict[str, Any],
    facts: list[str],
    as_is_flow: dict[str, Any] | None = None,
    to_be_flow: dict[str, Any] | None = None,
    source_refs: list[dict[str, str]] | None = None,
    missing_note: str = "Not named in the conversations. Recorded as an open item rather than guessed.",
) -> list[dict[str, Any]]:
    refs = source_refs or []
    bc = business_case
    scores = quality_scores
    weeks = estimate.get("effort_weeks") or {}
    glance = [
        {"label": "Automation", "value": cover.get("automation") or cover.get("title") or ""},
        {
            "label": "Expected benefit",
            "value": _expected_benefit_cell(bc, missing_note),
        },
        {
            "label": "Investment",
            "value": (
                f"~EUR {estimate.get('build_cost_eur')} build "
                f"({weeks.get('likely')} weeks) · ~EUR {bc.get('run_cost_eur_mo')}/month run cost"
            ),
        },
        {
            "label": "Payback",
            "value": (
                f"{_payback_cell(bc, missing_note)} · ROI over 36 months: ~{bc.get('roi_36m_pct')} %"
                if bc.get("payback_months") is not None
                else _payback_cell(bc, missing_note)
            ),
        },
        {
            "label": "Complexity",
            "value": f"Tier {estimate.get('tier')} · {len(systems)} systems · {len(rules)} named rules",
        },
        {"label": "Human in the loop", "value": cover.get("hitl") or "Exceptions stay with people."},
        {"label": "Security", "value": cover.get("security") or _security_summary(cover, missing_note)},
        {
            "label": "Data basis",
            "value": (
                f"Opportunity rating {scores.get('opportunity_rating')}/100 · "
                f"conversation quality {scores.get('conversation_quality')}/100 · "
                f"build-readiness {scores.get('build_readiness')}/100"
            ),
        },
    ]

    sensitivity_rows = []
    automation_label = _automation_metric_label(cover.get("title") or cover.get("automation"))
    for key, label in (("low", "Pessimistic"), ("expected", "Expected"), ("high", "Optimistic")):
        row = (bc.get("sensitivity") or {}).get(key) or {}
        sensitivity_rows.append(
            {
                "label": label,
                "detail": (
                    f"{automation_label} {_format_automation_rate_pct(row.get('automation_rate'))} · "
                    f"net ~EUR {row.get('net_eur_mo')}/month · "
                    f"payback {_payback_cell(row, missing_note)}"
                ),
            }
        )

    as_is = as_is_flow or _default_flow("As-is process", ["Intake", "Capture", "Check", "Post or clarify"])
    to_be = to_be_flow or _default_flow("To-be process (stage 2)", ["Intake", "Extract", "Match", "Post or queue"])

    bodies: dict[str, list[dict[str, Any]]] = {
        "0": [
            {
                "block": "prose",
                "text": (
                    "For every automation opportunity it identifies, the Borek AI Suite generates exactly one "
                    "framework report like this. It is generated from the conversations with your team and is "
                    "human-confirmed before it is the signed customer report. No consultant writes it. "
                    "Every number in this report is traceable to its source. "
                    "Estimates are shown as ranges with a confidence level, never as false precision."
                ),
            },
            {
                "block": "bullets",
                "items": [
                    "What is it? — the task today (chapters 1-2)",
                    "Why do it? — aim, benefit and measurable success (chapter 3)",
                    "How does it work? — the solution, the to-be process, the rules (chapters 4-5)",
                    "How is it built technically? — systems and integrations at CIO depth (chapter 6)",
                    "What do we need from you? — access, data, people (chapter 7)",
                    "Is it safe? — data protection, compliance, human control (chapter 8)",
                    "Does it pay? — business case, ROI, complexity (chapters 9-10)",
                    "Can we trust the numbers? — quality gates, open points, evolution (chapters 11-12)",
                ],
            },
        ],
        "1": [
            {
                "block": "prose",
                "text": cover.get("summary")
                or (facts[0] if facts else "The conversations describe a repeatable task that can be automated within named rules."),
            },
            {"block": "kv_rows", "caption": "At a glance", "rows": glance},
            {
                "block": "prose",
                "text": cover.get("how_produced")
                or "This report was generated from the captured conversations and the Suite engines. Missing facts are listed as open items.",
            },
            {
                "block": "callout",
                "kind": "recommendation",
                "text": cover.get("recommendation")
                or (
                    "Release for build at evolution stage 2 (autonomous with human control) only if all three "
                    "quality gates pass. Blocking items are listed in chapter 11; numbered next steps are in chapter 13."
                ),
            },
        ],
        "2": [
            {
                "block": "prose",
                "text": "This is how the work runs today — captured with the people who do it, not reconstructed later.",
            },
            as_is,
            {
                "block": "kv_rows",
                "caption": "What the current process costs",
                "rows": [
                    {"label": "Volume", "value": _or_missing(cover.get("volume"), missing_note)},
                    {"label": "Capacity tied up", "value": _or_missing(cover.get("capacity"), missing_note)},
                    {"label": "Clean-case handling time", "value": _or_missing(cover.get("clean_handling_time"), missing_note)},
                    {"label": "Exception handling time", "value": _or_missing(cover.get("exception_handling_time"), missing_note)},
                    {"label": "Exception rate", "value": _or_missing(cover.get("exception_rate"), missing_note)},
                    {"label": "Staff involved", "value": _or_missing(cover.get("staff_description"), missing_note)},
                    {"label": "Quality risk", "value": _or_missing(cover.get("quality_risk"), missing_note)},
                ],
            },
        ],
        "3": [
            {
                "block": "prose",
                "text": (
                    "The aim is a measurable state. These KPIs are a conservative derivation from the "
                    "conversations; empty cells are open items, not guesses."
                ),
            },
            {
                "block": "table",
                "caption": "Aim & success measurement",
                "columns": ["KPI", "Today (baseline)", "Target after 3 months", "Measured via"],
                "rows": [
                    [item.get("name", ""), item.get("baseline", ""), item.get("target", ""), item.get("measured_via", "")]
                    for item in kpis
                ]
                or [[missing_note, "—", "—", "—"]],
            },
        ],
        "4": [
            {
                "block": "prose",
                "text": "The workflow handles the standard case and pre-sorts everything else — with a reason, so clarification is quick.",
            },
            to_be,
            {
                "block": "table",
                "caption": "Today vs with the agent",
                "columns": ["Today", "With the agent"],
                "rows": _today_vs_agent_rows(as_is, to_be, cover),
            },
        ],
        "5": [
            {
                "block": "prose",
                "text": "The rules below come from the conversations. The agent invents no rules — it applies only what was named and confirmed.",
            },
            {
                "block": "kv_rows",
                "caption": "Trigger, inputs, result",
                "rows": [
                    {"label": "Trigger", "value": _or_missing(cover.get("trigger"), missing_note)},
                    {"label": "Inputs", "value": _or_missing(cover.get("inputs"), missing_note)},
                    {"label": "Result", "value": _or_missing(cover.get("result"), missing_note)},
                ],
            },
            {
                "block": "table",
                "caption": "The checking rules",
                "columns": ["Rule", "How the agent decides"],
                "rows": [[item.get("name", ""), item.get("logic", "")] for item in rules] or [[missing_note, "—"]],
            },
            {
                "block": "table",
                "caption": "The exceptions and how they are handled",
                "columns": ["Exception", "Frequency", "Handling"],
                "rows": [
                    [item.get("name", ""), item.get("frequency", ""), item.get("handling", "")]
                    for item in exceptions
                ]
                or [[missing_note, "—", "—"]],
            },
            {
                "block": "callout",
                "kind": "important",
                "text": "In no exception does the agent act on its own toward counterparties. It prepares the decision; your team decides.",
            },
        ],
        "6": [
            {
                "block": "prose",
                "text": "This chapter gives IT and the system owner the technical picture at the depth needed to say yes — without implementation detail.",
            },
            {
                "block": "table",
                "caption": "Systems landscape and data flow",
                "columns": ["System", "Role in the automation", "Dir.", "Access path", "Data"],
                "rows": [
                    [
                        item.get("name", ""),
                        item.get("role", ""),
                        item.get("direction", ""),
                        item.get("access_path", ""),
                        item.get("data_classification", ""),
                    ]
                    for item in systems
                ]
                or [[missing_note, "—", "—", "—", "—"]],
            },
            {
                "block": "table",
                "caption": "Building blocks",
                "columns": ["Building block", "Role in the automation", "How it is protected"],
                "rows": [
                    [
                        item.get("name", ""),
                        item.get("role", ""),
                        item.get("protection") or _building_block_protection(item, missing_note),
                    ]
                    for item in systems
                ]
                or [[missing_note, "—", "—"]],
            },
            {
                "block": "ai_split",
                "used_for": cover.get("ai_used_for")
                or ["Reading variable documents into structured fields with a confidence per field"],
                "not_used_for": cover.get("ai_not_used_for")
                or [
                    "Deciding whether a case matches",
                    "Evaluating tolerances or thresholds",
                    "Assessing any employee",
                ],
            },
        ],
        "7": [
            {
                "block": "prose",
                "text": "To deliver we need the following access, data and people on your side. Nothing here is invented.",
            },
            {
                "block": "table",
                "caption": "What we need from the client",
                "columns": ["Category", "Specifically", "Status", "Owner", "Hours"],
                "rows": [
                    [
                        item.get("category", ""),
                        item.get("detail", ""),
                        item.get("status", ""),
                        item.get("owner", ""),
                        _hours_cell(item, missing_note),
                    ]
                    for item in access_needs
                ]
                or [[missing_note, "—", "—", "—", missing_note]],
            },
        ],
        "8": [
            {
                "block": "kv_rows",
                "caption": "Binding guardrails",
                "rows": [
                    {"label": "Data classification", "value": _or_missing(cover.get("classification"), missing_note)},
                    {"label": "Data residency", "value": _or_missing(cover.get("residency"), missing_note)},
                    {"label": "Data minimization", "value": _or_missing(cover.get("minimization"), missing_note)},
                    {"label": "Access", "value": _or_missing(cover.get("access"), missing_note)},
                    {"label": "Audit", "value": _or_missing(cover.get("audit"), "Every decision logged.")},
                    {
                        "label": "Retention",
                        "value": _or_missing(
                            cover.get("retention"),
                            "Retention follows the named classification and residency guardrails; no extra copies beyond audit need.",
                        ),
                    },
                    {
                        "label": "Human control",
                        "value": _or_missing(cover.get("hitl"), "Exceptions and gated writes stay with people."),
                    },
                    {
                        "label": "What the agent never does",
                        "value": "No evaluation of employees — the agent measures work, never people. No unsourced rule changes.",
                    },
                    {
                        "label": "Breach",
                        "value": "A breach of these guardrails is a failed acceptance test.",
                    },
                ],
            }
        ],
        "9": [
            {
                "block": "prose",
                "text": "All values are calculated from the volumes and times your team reported — formulas disclosed, assumptions marked.",
            },
            {
                "block": "table",
                "caption": "Business case",
                "columns": ["Item", "Calculation", "Value"],
                "rows": [
                    [
                        "Effort today",
                        "automatable hours/month from the conversations",
                        f"~{bc.get('inputs', {}).get('automatable_hours_mo')} h/month",
                    ],
                    [
                        "Automation rate",
                        *_automation_rate_row(bc, missing_note),
                    ],
                    ["Hours saved / month", bc.get("formulas", {}).get("hours_saved_mo", ""), f"~{bc.get('hours_saved_mo')} h"],
                    ["Gross value", bc.get("formulas", {}).get("gross_eur_mo", ""), f"~EUR {bc.get('gross_eur_mo')}/month"],
                    ["Run cost", "archetype volume lookup", f"~EUR {bc.get('run_cost_eur_mo')}/month"],
                    ["Net value", bc.get("formulas", {}).get("net_eur_mo", ""), f"~EUR {bc.get('net_eur_mo')}/month"],
                    ["Build cost", "effort weeks x builder rate", f"~EUR {estimate.get('build_cost_eur')} one-off"],
                    ["Payback", bc.get("formulas", {}).get("payback_months", ""), _payback_cell(bc, missing_note)],
                    ["ROI 36 months", bc.get("formulas", {}).get("roi_36m_pct", ""), f"~{bc.get('roi_36m_pct')} %"],
                ],
            },
            {"block": "bullets", "items": bc.get("qualitative") or ["Qualitative benefits were not priced in."]},
            {"block": "sensitivity", "rows": sensitivity_rows},
        ],
        "10": [
            {
                "block": "prose",
                "text": "The week plan is for the recommended evolution stage in chapter 12, not for unsourced stage-3 scope.",
            },
            {
                "block": "kv_rows",
                "caption": "Classification",
                "rows": [
                    {"label": "Complexity tier", "value": str(estimate.get("tier", ""))},
                    {
                        "label": "Effort",
                        "value": (
                            f"{weeks.get('min')} – {weeks.get('likely')} – {weeks.get('max')} weeks "
                            f"(min / likely / max) · confidence: {estimate.get('confidence')}"
                        ),
                    },
                    {"label": "Team", "value": ", ".join(estimate.get("team") or [])},
                    {
                        "label": "Drivers",
                        "value": "; ".join(estimate.get("assumptions") or []) or missing_note,
                    },
                    {"label": "Build cost", "value": f"~EUR {estimate.get('build_cost_eur')}"},
                ],
            },
            {
                "block": "timeline",
                "weeks": _build_timeline_weeks(weeks, cover),
            },
        ],
        "11": [
            {
                "block": "prose",
                "text": "Before anything is built, every automation must pass three independent checks. You see all three results openly.",
            },
            {
                "block": "score_bars",
                "items": [
                    {
                        "name": "Opportunity rating",
                        "score": scores.get("opportunity_rating", 0),
                        "max": 100,
                        "band": "Is it worth doing?",
                        "explanation": (scores.get("rationale") or {}).get("opportunity_rating", ""),
                    },
                    {
                        "name": "Conversation quality",
                        "score": scores.get("conversation_quality", 0),
                        "max": 100,
                        "band": "Can we trust the data?",
                        "explanation": (scores.get("rationale") or {}).get("conversation_quality", ""),
                    },
                    {
                        "name": "Build-readiness",
                        "score": scores.get("build_readiness", 0),
                        "max": 100,
                        "band": "Is the concept buildable?",
                        "explanation": (scores.get("rationale") or {}).get("build_readiness", ""),
                    },
                ],
            },
            {
                "block": "table",
                "caption": "Open items and assumptions",
                "columns": ["Open item / assumption", "Type", "Owner", "Consequence if different"],
                "rows": [
                    [
                        item.get("description", ""),
                        item.get("item_type", ""),
                        item.get("owner", ""),
                        item.get("consequence_if_different", ""),
                    ]
                    for item in open_items
                ]
                or [["None recorded", "—", "—", "—"]],
            },
            {
                "block": "callout",
                "kind": "principle",
                "text": "Missing information is never guessed. Every gap appears here as an open item with an owner.",
            },
        ],
        "12": [
            {
                "block": "prose",
                "text": "Every automation is designed as a path, not an end state. You decide anew at each stage.",
            },
            {
                "block": "table",
                "caption": "Evolution stages",
                "columns": ["Stage", "What the agent does", "Human", "Benefit", "Extra effort"],
                "rows": [
                    [
                        item.get("stage_name", ""),
                        item.get("agent_does", ""),
                        item.get("human_does", ""),
                        item.get("benefit", ""),
                        item.get("extra_effort", ""),
                    ]
                    for item in evolution_stages
                ],
            },
            {
                "block": "callout",
                "kind": "note",
                "text": "Stage-3 elements are proposals only. They are never included in the committed business case.",
            },
        ],
        "13": [
            {
                "block": "table",
                "caption": "Next steps",
                "columns": ["#", "Step", "Who", "When"],
                "rows": cover.get("next_steps")
                or [
                    ["1", "Business confirmation of the captured process", "Business owner", "Before go"],
                    ["2", "Go decision in Deployment Control (this report is the decision basis)", "Sponsor", "This week"],
                    ["3", "Build with interim acceptance of stage 1", "Borek delivery + business", f"{weeks.get('likely')} weeks"],
                ],
            },
            {
                "block": "glossary",
                "terms": _build_domain_glossary(
                    cover=cover,
                    systems=systems,
                    rules=rules,
                    kpis=kpis,
                    facts=facts,
                ),
            },
        ],
    }

    chapters: list[dict[str, Any]] = []
    for chapter_id, title in load_chapter_registry():
        chapters.append(
            {
                "chapter_id": chapter_id,
                "title": title,
                "body": bodies[chapter_id],
                "source_refs": list(refs),
            }
        )
    return chapters


_EIGHT_QUESTION_MARKERS = (
    "what is it",
    "why do it",
    "how does it work",
    "how is it built",
    "what do we need",
    "is it safe",
    "does it pay",
    "can we trust",
)
_MISSING_NOTE = "Not named in the conversations. Recorded as an open item rather than guessed."


def overlay_llm_chapters(
    base_chapters: list[dict[str, Any]],
    llm_chapters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(chapter.get("chapter_id")): chapter for chapter in llm_chapters}
    merged: list[dict[str, Any]] = []
    for chapter in base_chapters:
        replacement = by_id.get(str(chapter["chapter_id"]))
        if not replacement:
            merged.append(chapter)
            continue
        body = replacement.get("body")
        if not body:
            merged.append(chapter)
            continue
        updated = dict(chapter)
        updated["body"] = _keep_required_blocks(str(chapter["chapter_id"]), chapter.get("body") or [], body)
        refs = replacement.get("source_refs") or chapter.get("source_refs")
        updated["source_refs"] = refs
        merged.append(updated)
    return merged


def _keep_required_blocks(chapter_id: str, base_body: list[dict[str, Any]], llm_body: Any) -> list[dict[str, Any]]:
    """Fill missing checklist fields in the LLM body. Never append a second copy of a block that already exists."""
    merged = list(llm_body) if isinstance(llm_body, list) else list(base_body)

    def blob() -> str:
        return str(merged).lower()

    def missing(block_type: str) -> bool:
        return not any(isinstance(item, dict) and item.get("block") == block_type for item in merged)

    def append_base(block_type: str) -> None:
        for item in base_body:
            if isinstance(item, dict) and item.get("block") == block_type:
                merged.append(item)
                return

    def kv_labels() -> str:
        return " ".join(
            str(row.get("label", ""))
            for item in merged
            if isinstance(item, dict) and item.get("block") == "kv_rows"
            for row in (item.get("rows") or [])
            if isinstance(row, dict)
        ).lower()

    if chapter_id == "0":
        _ensure_eight_questions(merged, base_body)
        _ensure_about_phrases(merged, base_body)
        _ensure_about_boilerplate_prose(merged, base_body)
        _remove_premature_confirmation_claim(merged)
    if chapter_id == "1":
        if missing("kv_rows"):
            append_base("kv_rows")
        else:
            _replace_first_block(merged, base_body, "kv_rows")
        if missing("callout"):
            append_base("callout")
        else:
            _patch_callout(
                merged,
                require_any=("stage",),
                require_one_of=("chapter 11", "open item", "blocking"),
                fallback=_first_block(base_body, "callout"),
            )
    if chapter_id == "2":
        _ensure_typed_process_flow(merged, base_body)
        if missing("kv_rows"):
            append_base("kv_rows")
        else:
            _replace_first_block(merged, base_body, "kv_rows")
    if chapter_id == "3":
        _ensure_kpi_table(merged, base_body)
        if "conservative" not in blob():
            _patch_or_append_prose(merged, base_body)
        _ensure_conservative_kpi_prose(merged, base_body)
    if chapter_id == "4":
        _ensure_typed_process_flow(merged, base_body)
        if "stage" not in blob():
            _tag_process_flow_stage(merged)
        _ensure_today_vs_agent_table(merged, base_body)
    if chapter_id == "5":
        labels = kv_labels()
        if any(token not in labels for token in ("trigger", "input", "result")):
            if missing("kv_rows"):
                append_base("kv_rows")
            else:
                _merge_kv_rows(merged, base_body, required_substrings=("trigger", "input", "result"))
        _ensure_table_purpose(merged, base_body, "rules")
        _ensure_table_purpose(merged, base_body, "exceptions")
        if "conversation" not in blob() and "transcript" not in blob() and "named" not in blob():
            _patch_or_append_prose(merged, base_body)
        if missing("callout") or not any(
            token in blob() for token in ("on its own", "people decide", "team decides")
        ):
            if missing("callout"):
                append_base("callout")
            else:
                _patch_callout(
                    merged,
                    require_any=("on its own", "people decide", "team decides"),
                    require_one_of=(),
                    fallback=_first_block(base_body, "callout"),
                )
    if chapter_id == "6":
        if missing("ai_split"):
            append_base("ai_split")
        _ensure_table_purpose(merged, base_body, "systems")
        _ensure_table_purpose(merged, base_body, "building_blocks")
        _ensure_table_protection(merged, base_body)
    if chapter_id == "7":
        if missing("table"):
            append_base("table")
        else:
            _ensure_client_hours_column(merged, base_body)
            _ensure_client_access_categories(merged, base_body)
    if chapter_id == "8":
        if missing("kv_rows"):
            append_base("kv_rows")
        else:
            _merge_kv_rows(
                merged,
                base_body,
                required_substrings=(
                    "classification",
                    "residency",
                    "audit",
                    "human",
                    "retention",
                    "employee",
                    "breach",
                ),
            )
        _replace_missing_notes_from_base(merged, base_body)
    if chapter_id == "9":
        # ES-23: calculations are deterministic engine output; Claude may
        # explain them in prose but cannot leave a contradictory calculation
        # narrative, callout, table, or scenario behind.
        merged[:] = list(base_body)
    if chapter_id == "10":
        if missing("kv_rows"):
            append_base("kv_rows")
        else:
            # ES-24: Claude may return the complexity table but omit one of its
            # required fields. Preserve the customer-facing draft while restoring
            # each mandatory planning field from the deterministic, sourced base.
            _merge_kv_rows(
                merged,
                base_body,
                required_substrings=("complexity", "effort", "confidence", "team", "driver"),
            )
        if missing("timeline"):
            append_base("timeline")
        if "chapter 12" not in blob() and "ch.12" not in blob():
            _patch_or_append_prose(merged, base_body)
    if chapter_id == "11":
        # ES-25 scores and their rationale are engine-owned and must not
        # coexist with stale LLM prose based on an earlier input set.
        merged[:] = list(base_body)
    if chapter_id == "12":
        # ES-26 evolution is generated from sourced candidates, never from
        # a second unsynchronised narrative.
        merged[:] = list(base_body)
    if chapter_id == "13":
        if missing("table"):
            append_base("table")
        _replace_first_block(merged, base_body, "glossary")
    return merged


def _blocks(body: list[dict[str, Any]], block_type: str) -> list[dict[str, Any]]:
    return [item for item in body if isinstance(item, dict) and item.get("block") == block_type]


def _first_block(body: list[dict[str, Any]], block_type: str) -> dict[str, Any] | None:
    for item in _blocks(body, block_type):
        return item
    return None


def _replace_first_block(
    merged: list[dict[str, Any]],
    base_body: list[dict[str, Any]],
    block_type: str,
    *,
    purpose: str | None = None,
) -> None:
    """Restore a deterministic block after prose-oriented LLM synthesis."""
    def matches(block: dict[str, Any]) -> bool:
        return block.get("block") == block_type and (purpose is None or _table_purpose(block) == purpose)

    base = next((block for block in base_body if isinstance(block, dict) and matches(block)), None)
    if base is None:
        return
    existing = next((block for block in merged if isinstance(block, dict) and matches(block)), None)
    if existing is None:
        merged.append(base)
    else:
        merged[merged.index(existing)] = base


def _remove_premature_confirmation_claim(merged: list[dict[str, Any]]) -> None:
    """A draft cannot state that human confirmation already occurred (ES-14)."""
    for block in _blocks(merged, "prose"):
        text = str(block.get("text") or "")
        block["text"] = re.sub(
            r"\bthen(?:\s+reviewed and)?\s+confirmed by a human (?:analyst|reviewer)\b",
            "and is ready for human review and confirmation",
            text,
            flags=re.I,
        )


def _ensure_eight_questions(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    canonical = _first_block(base_body, "bullets")
    if not canonical:
        return
    existing = _blocks(merged, "bullets")
    items: list[str] = []
    for block in existing:
        items.extend(str(item) for item in (block.get("items") or []))
    joined = " ".join(items).lower()
    has_all = len(items) >= 8 and all(marker in joined for marker in _EIGHT_QUESTION_MARKERS)
    if has_all and len(existing) == 1:
        return
    if existing:
        existing[0]["items"] = list(canonical.get("items") or [])
        for extra in existing[1:]:
            merged.remove(extra)
        return
    merged.append(canonical)


def _ensure_conservative_kpi_prose(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    """ES-17 — Ch.3 must state KPIs are a conservative derivation."""
    if "conservative" in str(merged).lower():
        return
    base_prose = _first_block(base_body, "prose")
    if base_prose:
        merged.insert(0, dict(base_prose))


def _ensure_about_boilerplate_prose(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    """ES-14 — deterministic Ch.0 must retain ranges / traceability boilerplate after LLM overlay."""
    base_prose = _first_block(base_body, "prose")
    if not base_prose:
        return
    blob = str(merged).lower()
    if "false precision" in blob and "traceable" in blob and ("range" in blob or "ranges" in blob):
        return
    prose = _first_block(merged, "prose")
    if prose and prose is not base_prose:
        merged.insert(0, dict(base_prose))
        return
    if not prose:
        merged.insert(0, dict(base_prose))


def _ensure_about_phrases(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    blob = str(merged).lower()
    missing_bits: list[str] = []
    if "generated" not in blob:
        missing_bits.append("This report is generated from the conversations with your team.")
    if "human-confirmed" not in blob and "human confirmed" not in blob:
        missing_bits.append("It is human-confirmed before it is the signed customer report.")
    if "traceable" not in blob and "source" not in blob:
        missing_bits.append("Every number in this report is traceable to its source.")
    if "range" not in blob and "ranges" not in blob:
        missing_bits.append("Estimates are shown as ranges with a confidence level.")
    if "false precision" not in blob and "false-precision" not in blob:
        missing_bits.append("Estimates are never shown as false precision.")
    if not missing_bits:
        return
    prose = _first_block(merged, "prose")
    addition = " ".join(missing_bits)
    if prose:
        prose["text"] = (str(prose.get("text") or "").rstrip() + " " + addition).strip()
        return
    base_prose = _first_block(base_body, "prose")
    if base_prose:
        merged.append(base_prose)


def _patch_or_append_prose(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    base_prose = _first_block(base_body, "prose")
    if not base_prose:
        return
    prose = _first_block(merged, "prose")
    addition = str(base_prose.get("text") or "").strip()
    if not addition:
        return
    if prose:
        current = str(prose.get("text") or "")
        if addition.lower() not in current.lower():
            prose["text"] = (current.rstrip() + " " + addition).strip()
        return
    merged.append(base_prose)


def _merge_kv_rows(
    merged: list[dict[str, Any]],
    base_body: list[dict[str, Any]],
    *,
    required_substrings: tuple[str, ...],
) -> None:
    existing = _first_block(merged, "kv_rows")
    base_kv = _first_block(base_body, "kv_rows")
    if existing is None:
        if base_kv:
            merged.append(base_kv)
        return
    blob = str(existing).lower()
    if all(token in blob for token in required_substrings):
        return
    if not base_kv:
        return
    have = {str(row.get("label", "")).lower() for row in (existing.get("rows") or []) if isinstance(row, dict)}
    rows = list(existing.get("rows") or [])
    for token in required_substrings:
        if token in blob:
            continue
        for row in base_kv.get("rows") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label", "")).lower()
            if token in str(row).lower() and label not in have:
                rows.append(row)
                have.add(label)
                blob += " " + str(row).lower()
                break
    existing["rows"] = rows


def _replace_missing_notes_from_base(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    base_kv = _first_block(base_body, "kv_rows")
    if not base_kv:
        return
    named = {
        str(row.get("label", "")).lower(): str(row.get("value") or "")
        for row in (base_kv.get("rows") or [])
        if isinstance(row, dict)
    }
    for block in _blocks(merged, "kv_rows"):
        for row in block.get("rows") or []:
            if not isinstance(row, dict):
                continue
            value = str(row.get("value") or "")
            if _MISSING_NOTE.lower() not in value.lower():
                continue
            replacement = named.get(str(row.get("label", "")).lower(), "")
            if replacement and _MISSING_NOTE.lower() not in replacement.lower():
                row["value"] = replacement


def _patch_callout(
    merged: list[dict[str, Any]],
    *,
    require_any: tuple[str, ...],
    require_one_of: tuple[str, ...],
    fallback: dict[str, Any] | None,
) -> None:
    callout = _first_block(merged, "callout")
    if callout is None:
        if fallback:
            merged.append(fallback)
        return
    text = str(callout.get("text") or "")
    lower = text.lower()
    extra: list[str] = []
    if require_any and not any(token in lower for token in require_any):
        extra.append(str((fallback or {}).get("text") or "").strip())
    if require_one_of and not any(token in lower for token in require_one_of):
        extra.append(str((fallback or {}).get("text") or "").strip())
    addition = " ".join(part for part in extra if part)
    if addition and addition.lower() not in lower:
        callout["text"] = (text.rstrip() + " " + addition).strip()


def _tag_process_flow_stage(merged: list[dict[str, Any]]) -> None:
    flow = _first_block(merged, "process_flow")
    if not flow:
        return
    caption = str(flow.get("caption") or "").strip()
    if "stage" not in caption.lower():
        flow["caption"] = f"{caption} (stage 2)".strip()


def _table_purpose(block: dict[str, Any]) -> str:
    text = f"{block.get('caption', '')} {' '.join(str(col) for col in (block.get('columns') or []))}".lower()
    if "building block" in text:
        return "building_blocks"
    if "exception" in text:
        return "exceptions"
    if "rule" in text or "checking" in text:
        return "rules"
    if "system" in text or "landscape" in text or "data flow" in text:
        return "systems"
    if "need" in text or "client" in text:
        return "client_needs"
    if "today" in text:
        return "today_vs"
    if "business case" in text or "calculation" in text:
        return "business_case"
    return str(block.get("caption") or "").lower().strip()


def _ensure_table_purpose(merged: list[dict[str, Any]], base_body: list[dict[str, Any]], purpose: str) -> None:
    if any(_table_purpose(item) == purpose for item in _blocks(merged, "table")):
        return
    for item in _blocks(base_body, "table"):
        if _table_purpose(item) == purpose:
            merged.append(item)
            return


def _ensure_table_protection(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    """ES-20: each customer-facing building block states its protection."""
    building = next((item for item in _blocks(merged, "table") if _table_purpose(item) == "building_blocks"), None)
    protections = [
        str(row[2] if len(row) > 2 else "").strip().lower()
        for row in (building or {}).get("rows") or []
        if isinstance(row, list)
    ]
    if building is not None and protections and all(
        protection and "as named" not in protection and "chapter 8" not in protection
        for protection in protections
    ):
        return
    base = next((item for item in _blocks(base_body, "table") if _table_purpose(item) == "building_blocks"), None)
    if base is None:
        return
    if building is None:
        merged.append(base)
    else:
        merged[merged.index(building)] = base


def _ensure_typed_process_flow(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    valid_kinds = {"agent", "human", "system", "decision", "start_end"}
    flow = _first_block(merged, "process_flow")
    nodes = (flow or {}).get("nodes") or []
    valid = len(nodes) >= 2 and all(
        isinstance(node, dict) and str(node.get("kind") or "") in valid_kinds for node in nodes
    )
    if valid:
        return
    fallback = _first_block(base_body, "process_flow")
    if fallback is None:
        return
    if flow is None:
        merged.append(fallback)
    else:
        merged[merged.index(flow)] = fallback


def _ensure_kpi_table(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    table = _first_block(merged, "table")
    blob = str(table or {}).lower()
    if table is not None and "baseline" in blob and "target" in blob and ("measured" in blob or "method" in blob):
        return
    fallback = _first_block(base_body, "table")
    if fallback is None:
        return
    if table is None:
        merged.append(fallback)
    else:
        merged[merged.index(table)] = fallback


def _ensure_today_vs_agent_table(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    if any("today" in str(item).lower() and "agent" in str(item).lower() for item in _blocks(merged, "table")):
        return
    fallback = next(
        (item for item in _blocks(base_body, "table") if "today" in str(item).lower() and "agent" in str(item).lower()),
        None,
    )
    if fallback is not None:
        merged.append(fallback)


def _ensure_client_hours_column(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    table = _first_block(merged, "table")
    if table is None:
        base = _first_block(base_body, "table")
        if base:
            merged.append(base)
        return
    columns = [str(col) for col in (table.get("columns") or [])]
    joined = " ".join(columns).lower()
    if "hour" in joined and "status" in joined and "owner" in joined:
        return
    if "hour" not in joined:
        columns.append("Hours")
        table["columns"] = columns
        hours_by_detail = {}
        base_table = _first_block(base_body, "table")
        for row in (base_table or {}).get("rows") or []:
            if len(row) >= 5:
                hours_by_detail[str(row[1]).strip().lower()] = str(row[4])
        padded = []
        for row in table.get("rows") or []:
            cells = list(row)
            if len(cells) < len(columns):
                detail = str(cells[1]).strip().lower() if len(cells) > 1 else ""
                cells.append(hours_by_detail.get(detail, _MISSING_NOTE))
            padded.append(cells)
        table["rows"] = padded
    joined_cols = " ".join(str(col) for col in (table.get("columns") or [])).lower()
    if "status" not in joined_cols or "owner" not in joined_cols:
        base = _first_block(base_body, "table")
        if base is not None:
            merged[merged.index(table)] = base


def _ensure_client_access_categories(merged: list[dict[str, Any]], base_body: list[dict[str, Any]]) -> None:
    """ES-21: a refined Chapter 7 table cannot omit required client-access categories."""
    table = _first_block(merged, "table")
    base_table = _first_block(base_body, "table")
    if table is None or base_table is None:
        return
    required = (
        ("Read access", "read", ("read",)),
        ("Write access", "write", ("write",)),
        ("Sample / test data", "sample", ("sample", "test", "sandbox")),
        ("Rule confirmation", "rule", ("rule",)),
        ("Identity / SSO", "identity", ("identity", "sso")),
    )
    rows = [list(row) for row in table.get("rows") or []]
    for canonical_category, required_token, needles in required:
        existing = next(
            (
                row
                for row in rows
                if any(needle in str(row[0] if row else "").lower() for needle in needles)
            ),
            None,
        )
        if existing is not None:
            if required_token not in str(existing[0] if existing else "").lower():
                existing[0] = canonical_category
            continue
        fallback = next(
            (
                list(row)
                for row in base_table.get("rows") or []
                if any(needle in str(row[0] if row else "").lower() for needle in needles)
            ),
            None,
        )
        if fallback is not None:
            fallback[0] = canonical_category
            rows.append(fallback)
    table["rows"] = rows


def _today_vs_agent_rows(
    as_is: dict[str, Any],
    to_be: dict[str, Any],
    cover: dict[str, Any],
) -> list[list[str]]:
    as_nodes = [node for node in (as_is.get("nodes") or []) if isinstance(node, dict)]
    to_nodes = [node for node in (to_be.get("nodes") or []) if isinstance(node, dict)]
    if as_nodes and to_nodes:
        count = max(len(as_nodes), len(to_nodes))
        rows: list[list[str]] = []
        for index in range(count):
            today = str((as_nodes[index] if index < len(as_nodes) else {}).get("label") or "—")
            agent = str((to_nodes[index] if index < len(to_nodes) else {}).get("label") or "—")
            rows.append([today, agent])
        return rows
    return [
        [cover.get("today_intake") or "Manual intake", "Agent monitors the named intake path"],
        [cover.get("today_check") or "Manual check", "Named rules applied deterministically"],
        [cover.get("today_exceptions") or "Ad-hoc clarification", "Structured exception queue; people decide"],
    ]


def _build_timeline_weeks(weeks: dict[str, Any], cover: dict[str, Any]) -> list[dict[str, Any]]:
    if cover.get("timeline_weeks"):
        return cover["timeline_weeks"]
    likely = int(float(weeks.get("likely") or 3))
    span = max(likely, 3)
    chunk = max(1, span // 3)
    return [
        {"id": "W1", "items": [f"Weeks 1–{chunk}: connect intake, read paths, and samples"]},
        {"id": "W2", "items": [f"Weeks {chunk + 1}–{chunk * 2}: rules, exception queue, tests"]},
        {
            "id": "W3",
            "items": [f"Weeks {chunk * 2 + 1}–{span}: gated writes, audit, acceptance, go-live approval (chapter 12 stage 2)"],
        },
    ]


def _build_domain_glossary(
    *,
    cover: dict[str, Any],
    systems: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    kpis: list[dict[str, Any]],
    facts: list[str],
) -> list[dict[str, str]]:
    if cover.get("glossary"):
        return cover["glossary"]
    terms: list[dict[str, str]] = [
        {
            "term": _automation_metric_label(cover.get("title") or cover.get("automation")),
            "meaning": "Share of cases the workflow completes without a human step.",
        },
        {"term": "Exception queue", "meaning": "Cases that could not be resolved by rule, each with reason and a suggested action."},
        {"term": "Build-readiness", "meaning": "A 0-100 score of whether the concept is complete enough to build."},
        {"term": "Stage 1 / 2 / 3", "meaning": "Assistive · autonomous with human control · end-to-end (proposal)."},
    ]
    seen = {item["term"].lower() for item in terms}
    for source in (
        [item.get("name", "") for item in systems]
        + [item.get("name", "") for item in rules]
        + [item.get("name", "") for item in kpis]
        + facts[:3]
    ):
        label = str(source).strip()
        if not label or len(label) < 4:
            continue
        short = label if len(label) <= 48 else label[:48].rsplit(" ", 1)[0]
        key = short.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append({"term": short, "meaning": f"As named in the conversations: {label}."})
    return terms


def _security_summary(cover: dict[str, Any], missing_note: str) -> str:
    classification = str(cover.get("classification") or "").strip()
    residency = str(cover.get("residency") or "").strip()
    summary = " ".join(part for part in (classification, residency) if part)
    return summary or missing_note


def _building_block_protection(item: dict[str, Any], missing_note: str) -> str:
    access = str(item.get("access_path") or "").strip()
    classification = str(item.get("data_classification") or "").strip()
    parts: list[str] = []
    if access and access.lower() != "as reported":
        parts.append(f"Least-privilege access: {access}")
    if classification and classification.lower() != "as reported":
        parts.append(f"Data handling: {classification}")
    return "; ".join(parts) if parts else missing_note


def _default_flow(caption: str, labels: list[str]) -> dict[str, Any]:
    nodes = [{"id": f"n{index}", "label": label, "kind": "human" if index % 2 else "system"} for index, label in enumerate(labels)]
    edges = [{"from": f"n{index}", "to": f"n{index + 1}", "label": ""} for index in range(len(labels) - 1)]
    return {"block": "process_flow", "caption": caption, "nodes": nodes, "edges": edges}


def _automation_metric_label(title: str | None) -> str:
    lower = str(title or "").lower()
    if any(token in lower for token in ("invoice", "3-way", "3 way", "match")):
        return "Auto-match"
    return "Automation rate"


def _format_automation_rate_pct(rate: Any) -> str:
    if rate is None:
        return "an open item %"
    return f"{round(float(rate) * 100, 1):g} %"


def _automation_rate_row(bc: dict[str, Any], missing_note: str) -> tuple[str, str]:
    inputs = bc.get("inputs") or {}
    rate = inputs.get("automation_rate")
    formula = str(bc.get("formulas", {}).get("hours_saved_mo") or "")
    derived = "target remaining hours" in formula
    if rate is not None and float(rate) > 0:
        calculation = (
            "derived from the hour target in the conversations"
            if derived
            else "named auto-match / automation target"
        )
        return calculation, f"~{_format_automation_rate_pct(rate)}"
    return "named auto-match / automation target", missing_note


def _expected_benefit_cell(bc: dict[str, Any], missing_note: str) -> str:
    hours_saved = bc.get("hours_saved_mo")
    net = bc.get("net_eur_mo")
    if hours_saved is None or float(hours_saved) <= 0:
        return (
            f"{missing_note} (hours saved/month and net EUR value could not be calculated from the conversation)."
        )
    if net is None or float(net) <= 0:
        return f"~{hours_saved:g} h/month capacity reclaimed · net EUR value is an open item"
    return f"~{hours_saved:g} h/month capacity reclaimed · ~EUR {net:g} net value/month"


def _payback_cell(business_case: dict[str, Any], missing_note: str) -> str:
    months = business_case.get("payback_months")
    if months is None:
        return missing_note
    return f"~{months} months"


def _hours_cell(item: dict[str, Any], missing_note: str) -> str:
    named = str(item.get("hours") or "").strip()
    if named:
        return named
    match = re.search(r"(\d+(?:\.\d+)?)\s*h(?:ours?)?", str(item.get("detail") or ""), re.I)
    if match:
        return match.group(0)
    return missing_note


def _or_missing(value: Any, missing_note: str) -> str:
    text = str(value or "").strip()
    return text if text else missing_note
