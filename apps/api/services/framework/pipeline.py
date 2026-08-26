"""Customer-report pipeline: assemble → engines → (optional LLM) → validate → customer view."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

import jsonschema

from packages.contracts.validators import chapter_specs_from_registry
from services.framework.assembly import assemble_from_knowledge
from services.framework.business_case import compute_business_case
from services.framework.chapter_builder import build_chapters
from services.framework.chapter_validators import validate_all_chapters
from services.framework.chapter_validators.ch06_how_built import scrub_framework_chapter_6
from services.framework.config_loader import repo_root
from services.framework.cross_chapter_rules import enforce_cross_chapter_rules, flag_multi_process
from services.framework.customer_view import build_customer_view
from services.framework.eligibility import check_eligibility, render_decision
from services.framework.estimation import estimate_effort
from services.framework.evolution import generate_evolution
from services.framework.guardrails import convert_unsourced_claims, enforce_guardrails, strip_citations_from_value
from services.framework.pre_confirm_check import prepare_framework_for_confirm
from services.framework.process_scope import ProcessComplete, enforce_semantic_process_scope
from services.framework.source_traceability import attach_block_source_refs, convert_unsupported_block_claims
from services.framework.quality_scores import (
    assemble_quality_scores,
    score_build_readiness,
    score_conversation_quality,
    score_opportunity,
)
from services.framework.synthesis import (
    PROMPT_VERSION,
    apply_draft_to_chapters,
    synthesize_customer_draft,
)
from services.observability.llm_logger import STAGE_LOCALIZE, STAGE_PROCESS_SCOPE, STAGE_SYNTHESIS, jobs_for_opportunity

from services.framework.localization import make_localize_fn
from llm.claude.client import sonnet_model

ClaudeComplete = Callable[[str, str, dict[str, Any]], dict[str, Any]]


def generate_customer_framework(
    knowledge_models: list[dict[str, Any]],
    *,
    opportunity_id: str,
    title_hint: str | None = None,
    lang: str = "en",
    use_llm: bool = True,
    complete: ClaudeComplete | None = None,
    process_complete: ProcessComplete | None = None,
    engine_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Live generation must not reject a single process merely because two
    # domain keywords occur in one conversation. ES-29 is decided by Claude's
    # sourced semantic gate below; deterministic tests retain the fast guard.
    flag_multi_process(knowledge_models, opportunity_id, include_heuristics=not use_llm)
    process_scope: dict[str, Any] | None = None
    if use_llm and (complete is None or process_complete is not None):
        process_scope = enforce_semantic_process_scope(
            knowledge_models,
            opportunity_id=opportunity_id,
            complete=process_complete,
        )
    skeleton = assemble_from_knowledge(
        knowledge_models, opportunity_id=opportunity_id, title_hint=title_hint
    )
    engines = run_engines(skeleton, overrides=engine_overrides or {})
    if engines["business_case"].get("payback_months") is None:
        skeleton["open_items"] = _merge_open_items(
            skeleton.get("open_items") or [],
            [
                {
                    "description": "Payback in months cannot be calculated: automatable hours or net value were not named in the conversations.",
                    "item_type": "assumption",
                    "owner": "Business",
                    "consequence_if_different": "Missing information is never guessed. Confirm hours and volume before using a payback figure.",
                }
            ],
        )
    check_eligibility(
        conversation_quality=int(engines["conversation"]["score"]),
        has_knowledge=bool(skeleton.get("source_entries")),
        gaps=_gaps_from_open_items(skeleton.get("open_items") or []),
    )

    evolution = generate_evolution(
        today_description=skeleton.get("facts")[0] if skeleton.get("facts") else "Fully manual process.",
        stage2_agent_does=engines.get("stage2_agent_does")
        or "Runs the named standard case within confirmed rules; exceptions go to people.",
        stage2_human_does="Exceptions, gated approvals, spot checks.",
        stage2_benefit=f"~{engines['business_case']['hours_saved_mo']} h/month · full business case from chapter 9",
        stage2_effort=f"base build ({engines['estimate']['effort_weeks']['likely']} weeks, EUR {engines['estimate']['build_cost_eur']})",
        stage3_candidates=skeleton.get("stage3_candidates") or [],
    )

    cover = _cover_from_skeleton(skeleton, engines)
    source_refs = _collect_refs(skeleton.get("source_entries") or [])
    chapters = build_chapters(
        cover=cover,
        kpis=skeleton.get("kpis") or [],
        systems=skeleton.get("systems") or [],
        rules=skeleton.get("rules") or [],
        exceptions=skeleton.get("exceptions") or [],
        access_needs=skeleton.get("access_needs") or [],
        open_items=skeleton.get("open_items") or [],
        evolution_stages=evolution,
        quality_scores=engines["quality_scores"],
        estimate=engines["estimate"],
        business_case=engines["business_case"],
        facts=skeleton.get("facts") or [],
        source_refs=source_refs,
    )

    llm_meta = {"used": False, "model": None, "prompt_version": PROMPT_VERSION}
    if use_llm:
        draft = synthesize_customer_draft(
            skeleton=skeleton,
            engine_outputs=_engine_payload(engines, evolution),
            complete=complete,
            opportunity_id=opportunity_id,
        )
        chapters = apply_draft_to_chapters(chapters, draft)
        cover.update(draft.get("cover") or {})
        if draft.get("kpis"):
            skeleton["kpis"] = _merge_required_kpis(skeleton.get("kpis") or [], draft["kpis"])
        if draft.get("systems"):
            skeleton["systems"] = draft["systems"]
        if draft.get("rules"):
            skeleton["rules"] = draft["rules"]
        if draft.get("exceptions"):
            skeleton["exceptions"] = draft["exceptions"]
        if draft.get("access_needs"):
            skeleton["access_needs"] = draft["access_needs"]
        if draft.get("open_items"):
            skeleton["open_items"] = _merge_open_items(skeleton.get("open_items") or [], draft["open_items"])
        if draft.get("title"):
            skeleton["title"] = draft["title"]
        if draft.get("department"):
            skeleton["department"] = draft["department"]
        llm_meta = {"used": True, "model": sonnet_model(), "prompt_version": PROMPT_VERSION}

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    framework_id = f"FW-{opportunity_id}-v1"
    framework: dict[str, Any] = {
        "id": framework_id,
        "framework_id": framework_id,
        "schema_version": "1.0",
        "opportunity_id": opportunity_id,
        "title": skeleton["title"],
        "department": skeleton["department"],
        "status": "draft",
        "priority_rank": 1,
        "quality_scores": engines["quality_scores"],
        "kpis": skeleton.get("kpis") or [],
        "systems": skeleton.get("systems") or [],
        "rules": skeleton.get("rules") or [],
        "exceptions": skeleton.get("exceptions") or [],
        "access_needs": skeleton.get("access_needs") or [],
        "evolution_stages": evolution,
        "open_items": skeleton.get("open_items") or [],
        "chapters": chapters,
        "version": 1,
        "generated_from": skeleton.get("transcript_ids") or [],
        "previous_version_id": None,
        "change_log": ["Initial customer-report generation"],
        "created_at": now,
        "updated_at": now,
        "language_master": "en",
        "render_languages": ["de", "en"],
        "estimate": engines["estimate"],
        "business_case": engines["business_case"],
        "assessments": {
            "opportunity": engines["opportunity"],
            "conversation_quality": engines["conversation"],
            "build_readiness": engines["readiness"],
        },
        "cover": cover,
        "numbers": skeleton.get("numbers"),
        "source_entries": skeleton.get("source_entries") or [],
        "generation_meta": {
            "engine_version": "customer-report-v1",
            "ruleset_version": "scoring.config.json",
            "config_version": "estimation.config.json+business_case.config.json",
            "llm_model": llm_meta["model"] or "deterministic-builder",
            "prompt_version": llm_meta["prompt_version"],
            "llm_used": llm_meta["used"],
            "generated_at": now,
            "llm_job_log": jobs_for_opportunity(
                opportunity_id,
                stages=[STAGE_PROCESS_SCOPE, STAGE_SYNTHESIS] if process_scope else [STAGE_SYNTHESIS],
            )
            if llm_meta["used"]
            else [],
            "process_scope": process_scope,
        },
    }

    schema = json.loads((repo_root() / "packages" / "contracts" / "framework_object.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=framework, schema=schema)
    _assert_registry_titles(framework)
    scrub_framework_chapter_6(framework)
    prepare_framework_for_confirm(framework)
    attach_block_source_refs(framework, skeleton.get("source_entries") or [])
    validate_all_chapters(framework)
    convert_unsupported_block_claims(framework, skeleton.get("source_entries") or [])
    enforce_cross_chapter_rules(framework, skeleton.get("source_entries") or [])
    convert_unsourced_claims(framework)

    decision = render_decision(int(engines["readiness"]["score"]), framework.get("open_items") or [])
    framework["render"] = decision
    framework["readiness_band"] = decision["band"]
    status_label = {
        "not_ready": "BLOCKED",
        "ready_with_assumptions": "READY WITH ASSUMPTIONS",
        "ready_to_build": "READY TO BUILD",
    }[decision["band"]]
    framework["cover"]["status_label"] = status_label

    customer = build_customer_view(
        framework,
        lang=lang,
        localize=make_localize_fn(opportunity_id=opportunity_id, framework_id=framework_id)
        if lang == "de" and use_llm
        else None,
        opportunity_id=opportunity_id,
        framework_id=framework_id,
    )
    customer = strip_citations_from_value(customer)
    if decision["allowed"]:
        enforce_guardrails(framework, customer)
    framework["customer_view"] = customer
    framework["generation_meta"]["llm_job_log"] = jobs_for_opportunity(
        opportunity_id,
        stages=[STAGE_SYNTHESIS, STAGE_LOCALIZE],
    )
    return framework


def run_engines(skeleton: dict[str, Any], *, overrides: dict[str, Any]) -> dict[str, Any]:
    inputs = {**(skeleton.get("engine_inputs") or {}), **overrides}
    hours_mo = _optional_float(inputs, "hours_mo")
    automatable = _optional_float(inputs, "automatable_hours_mo")
    if hours_mo is None:
        hours_mo = automatable if automatable is not None else 0.0
    if automatable is None:
        automatable = hours_mo
    volume = _optional_float(inputs, "monthly_volume")
    if volume is None:
        volume = 0.0
    timeline = float(inputs.get("timeline_weeks") or 3)
    archetype = str(inputs.get("archetype") or "doc_extraction")
    data_readiness = str(inputs.get("data_readiness") or ("ready" if inputs.get("write_available") else "partial"))
    reuse = list(inputs.get("reuse") or ["library_component"])

    estimate = estimate_effort(
        archetype=archetype,
        step_count=int(inputs.get("step_count") or 5),
        system_count=int(inputs.get("system_count") or 1),
        rule_count=int(inputs.get("rule_count") or 0),
        hard_integration_count=int(inputs.get("hard_integration_count") or 0),
        data_readiness=data_readiness,
        reuse=reuse,
        builder_count=int(inputs.get("builder_count") or 1),
    )
    timeline = float(estimate["timeline_weeks"])

    opportunity = score_opportunity(
        hours_mo=hours_mo,
        timeline_weeks=timeline,
        strategic_fit_level=int(inputs.get("strategic_fit_level") or 3),
        feasibility_level=int(inputs.get("feasibility_level") or 2),
        risk_inverted_level=int(inputs.get("risk_inverted_level") or 2),
    )
    conversation = score_conversation_quality(
        result_quality=float(inputs.get("result_quality") or 90),
        information_richness=float(inputs.get("information_richness") or 85),
        engagement=float(inputs.get("engagement") or 65),
    )
    systems = skeleton.get("systems") or []
    intake_read = any("mailbox" in str(item.get("name", "")).lower() or item.get("direction") == "read" for item in systems)
    system_read = any(item.get("direction") in {"read", "read_write"} for item in systems)
    system_write = bool(inputs.get("write_available"))
    readiness = score_build_readiness(
        has_aim_metric=bool(skeleton.get("kpis")),
        functional_spec_complete=bool(skeleton.get("rules")),
        has_sample=bool(inputs.get("has_sample")),
        intake_read_available=bool(intake_read or systems),
        system_read_available=bool(system_read or systems),
        system_write_available=system_write,
        data_compliance_complete=bool(skeleton.get("constraints")),
        estimate_complete=True,
        business_case_complete=automatable > 0 and volume > 0,
        acceptance_complete=bool(skeleton.get("kpis")),
        blocker_open_questions=sum(1 for item in skeleton.get("open_items") or [] if item.get("item_type") == "dependency"),
    )
    business = compute_business_case(
        automatable_hours_mo=automatable,
        monthly_volume=volume,
        loaded_hourly_cost_eur=inputs.get("loaded_hourly_cost_eur"),
        automation_rate=inputs.get("automation_rate"),
        build_cost_eur=int(estimate["build_cost_eur"]),
        archetype=archetype,
        qualitative=list(inputs.get("qualitative") or []),
        extra_assumptions=list(estimate.get("assumptions") or []),
    )
    return {
        "opportunity": opportunity,
        "conversation": conversation,
        "readiness": readiness,
        "quality_scores": assemble_quality_scores(opportunity, conversation, readiness),
        "estimate": estimate,
        "business_case": business,
    }


def _engine_payload(engines: dict[str, Any], evolution: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "quality_scores": engines["quality_scores"],
        "estimate": engines["estimate"],
        "business_case": engines["business_case"],
        "evolution_stages": evolution,
    }


def _merge_required_kpis(base: list[dict[str, Any]], draft: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """LLM wording may refine KPIs, but cannot remove Lead-required categories."""
    merged = [item for item in draft if isinstance(item, dict)]
    categories = (
        ("automation", ("automation", "auto-match", "auto match")),
        ("manual", ("manual", "handling time", "hours")),
        ("quality", ("quality", "error", "wrong", "success")),
        ("cycle", ("cycle", "lead time", "close", "month-end")),
    )

    def has_category(items: list[dict[str, Any]], needles: tuple[str, ...]) -> bool:
        names = " ".join(str(item.get("name") or "").lower() for item in items)
        return any(needle in names for needle in needles)

    for _category, needles in categories:
        if has_category(merged, needles):
            continue
        fallback = next(
            (item for item in base if isinstance(item, dict) and has_category([item], needles)),
            None,
        )
        if fallback is not None:
            merged.append(dict(fallback))
    return merged


def _cover_from_skeleton(skeleton: dict[str, Any], engines: dict[str, Any]) -> dict[str, Any]:
    numbers = skeleton.get("numbers") or {}
    volume = numbers.get("monthly_volume")
    blob = str(numbers.get("blob") or "")
    texts = [
        *list(skeleton.get("constraints") or []),
        *list(skeleton.get("facts") or []),
        *list(skeleton.get("requirements") or []),
        *list(skeleton.get("people") or []),
    ]
    clean_time = _first_minutes(blob, ("clean", "standard", "straightforward"))
    exception_time = _first_minutes(blob, ("exception", "mismatch", "escalation"))
    exception_rate = _first_percent_text(blob)
    staff = _named_text(texts, "team") or _named_text(texts, "lead") or _named_text(texts, "owner")
    return {
        "title": skeleton.get("title"),
        "automation": skeleton.get("title"),
        "tagline": "The framework report from the customer's point of view.",
        "sources_line": "Sources " + ", ".join(skeleton.get("conversation_ids") or []),
        "how_produced": "Generated automatically from the captured conversations. Missing facts are listed, never guessed.",
        "volume": f"~{volume}/month" if volume else "",
        "capacity": (
            f"~{engines['business_case']['inputs']['automatable_hours_mo']} hours/month in the automatable core"
            if engines["business_case"]["inputs"].get("automatable_hours_mo")
            else ""
        ),
        "clean_handling_time": clean_time,
        "exception_handling_time": exception_time,
        "exception_rate": exception_rate,
        "staff_description": staff,
        "hitl": "Exceptions are always decided by people.",
        "recommendation": (
            "Release for build at evolution stage 2 (autonomous with human control) only if all three "
            "quality gates pass. Blocking items are listed in chapter 11; numbered next steps are in chapter 13."
        ),
        "classification": _named_text(texts, "classification", "confidential") or _named_text(texts, "confidential"),
        "residency": _named_text(texts, "residency") or _named_text(texts, "eu"),
        "retention": _named_text(texts, "retention") or _named_text(texts, "keep") or _named_text(texts, "archive"),
        "minimization": _named_text(texts, "iban") or _named_text(texts, "not kept") or _named_text(texts, "minimization"),
        "access": _named_text(texts, "least-privilege") or _named_text(texts, "least privilege"),
        "audit": _named_text(texts, "audit") or _named_text(texts, "logged"),
        "trigger": _named_text(texts, "mailbox") or _named_text(texts, "arrives"),
        "inputs": _named_text(texts, "purchase order") or _named_text(texts, "invoice"),
        "result": _named_text(texts, "posted") or _named_text(texts, "exception queue"),
    }


def _first_minutes(blob: str, needles: tuple[str, ...]) -> str:
    pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?)", re.I)
    for sentence in re.split(r"[.;]", blob):
        lower = sentence.lower()
        if any(needle in lower for needle in needles):
            match = pattern.search(sentence)
            if match:
                return f"{match.group(1)} minutes"
    match = pattern.search(blob)
    return f"{match.group(1)} minutes" if match else ""


def _first_percent_text(blob: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", blob, re.I)
    return f"{match.group(1)} %" if match else ""


def _named_text(texts: list[str], *needles: str) -> str:
    for text in texts:
        lower = str(text).lower()
        if all(needle in lower for needle in needles):
            return str(text)
    return ""


def _collect_refs(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        for ref in entry.get("source_refs") or []:
            key = (
                str(ref.get("conversation_id", "")),
                str(ref.get("speaker_role", "")),
                str(ref.get("excerpt_pointer", "")),
            )
            if key in seen or not all(key):
                continue
            seen.add(key)
            refs.append(
                {
                    "conversation_id": key[0],
                    "speaker_role": key[1],
                    "excerpt_pointer": key[2],
                }
            )
    return refs


def _merge_open_items(base: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {item.get("description") for item in base}
    merged = list(base)
    for item in extra:
        if item.get("description") not in seen:
            merged.append(item)
            seen.add(item.get("description"))
    return merged


def _gaps_from_open_items(open_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "missing_field": item.get("description"),
            "framework_block": "open_items",
            "route_to": "C6/C8",
            "blocker": item.get("item_type") == "dependency",
        }
        for item in open_items
    ]


def _assert_registry_titles(framework: dict[str, Any]) -> None:
    import json

    registry = json.loads((repo_root() / "packages" / "contracts" / "chapter_registry.json").read_text(encoding="utf-8"))
    expected = chapter_specs_from_registry(registry)
    actual = [(str(ch["chapter_id"]), ch["title"]) for ch in framework["chapters"]]
    if actual != expected:
        raise ValueError("Chapter ids/titles must match chapter_registry.json exactly.")


def _optional_float(inputs: dict[str, Any], key: str) -> float | None:
    if key not in inputs or inputs[key] is None or inputs[key] == "":
        return None
    return float(inputs[key])


def new_job_id() -> str:
    return str(uuid4())
