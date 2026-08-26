"""ES-11 — opportunity, conversation quality, and build-readiness as pure functions."""

from __future__ import annotations

from typing import Any

from services.framework.config_loader import scoring_config

USABLE_THRESHOLD = 75


def _normalize(level: int, mapping: dict[str, int]) -> int:
    return int(mapping[str(level)])


def _band_level(value: float, low: float, high: float, *, lower_is_better: bool = False) -> int:
    """Map a numeric value onto 1/2/3 using inclusive middle band [low, high]."""
    if lower_is_better:
        if value <= low:
            return 3
        if value <= high:
            return 2
        return 1
    if value < low:
        return 1
    if value <= high:
        return 2
    return 3


def score_opportunity(
    *,
    hours_mo: float,
    timeline_weeks: float,
    strategic_fit_level: int,
    feasibility_level: int,
    risk_inverted_level: int,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = (config or scoring_config())["opportunity"]
    mapping = {k: int(v) for k, v in cfg["normalize"].items()}
    impact_bands = cfg["impact_hours_bands"]
    speed_bands = cfg["speed_weeks_bands"]

    impact_level = _band_level(hours_mo, impact_bands[0], impact_bands[1])
    speed_level = _band_level(
        timeline_weeks, speed_bands[0], speed_bands[1], lower_is_better=True
    )

    dims = {
        "impact": _normalize(impact_level, mapping),
        "strategic_fit": _normalize(strategic_fit_level, mapping),
        "speed": _normalize(speed_level, mapping),
        "feasibility": _normalize(feasibility_level, mapping),
        "risk_inverted": _normalize(risk_inverted_level, mapping),
    }
    weights = cfg["weights"]
    score = round(sum(dims[name] * float(weights[name]) for name in dims))
    evidence = [
        f"impact from {hours_mo} h/month → level {impact_level}",
        f"speed from {timeline_weeks} weeks → level {speed_level}",
        f"strategic_fit level {strategic_fit_level}",
        f"feasibility level {feasibility_level}",
        f"risk_inverted level {risk_inverted_level}",
    ]
    return {
        "score": score,
        "dims": dims,
        "levels": {
            "impact": impact_level,
            "speed": speed_level,
            "strategic_fit": strategic_fit_level,
            "feasibility": feasibility_level,
            "risk_inverted": risk_inverted_level,
        },
        "evidence": evidence,
        "inputs": {
            "hours_mo": hours_mo,
            "timeline_weeks": timeline_weeks,
            "strategic_fit_level": strategic_fit_level,
            "feasibility_level": feasibility_level,
            "risk_inverted_level": risk_inverted_level,
        },
    }


def score_conversation_quality(
    *,
    result_quality: float,
    information_richness: float,
    engagement: float,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = (config or scoring_config())["conversation_quality"]
    weights = cfg["weights"]
    richness_bands = cfg["richness_slot_bands"]
    band_cuts = cfg["bands"]

    richness_pct = information_richness * 100 if information_richness <= 1 else information_richness
    result = _clamp(result_quality)
    richness = _clamp(richness_pct)
    engage = _clamp(engagement)

    score = round(
        result * float(weights["result_quality"])
        + richness * float(weights["information_richness"])
        + engage * float(weights["engagement"])
    )
    if score < int(band_cuts["needs_human_followup"]):
        band = "needs_human_followup"
    elif score <= int(band_cuts["usable"]):
        band = "usable"
    else:
        band = "strong"

    richness_level = _band_level(information_richness if information_richness <= 1 else information_richness / 100, richness_bands[0], richness_bands[1])
    return {
        "score": score,
        "dims": {
            "result_quality": result,
            "information_richness": richness,
            "engagement": engage,
        },
        "band": band,
        "richness_level": richness_level,
        "evidence": [
            f"result_quality={result}",
            f"information_richness={richness}",
            f"engagement={engage}",
        ],
        "inputs": {
            "result_quality": result,
            "information_richness": richness,
            "engagement": engage,
        },
    }


def score_build_readiness(
    *,
    has_aim_metric: bool,
    functional_spec_complete: bool,
    has_sample: bool,
    intake_read_available: bool,
    system_read_available: bool,
    system_write_available: bool,
    data_compliance_complete: bool,
    estimate_complete: bool,
    business_case_complete: bool,
    acceptance_complete: bool,
    blocker_open_questions: int,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = (config or scoring_config())["build_readiness"]
    weights = {k: int(v) for k, v in cfg["blocks"].items()}
    parts = cfg["integration_parts"]

    integration_score = 0
    if intake_read_available:
        integration_score += int(parts["mailbox_or_intake_read"])
    if system_read_available:
        integration_score += int(parts["system_of_record_read"])
    if system_write_available:
        integration_score += int(parts["system_of_record_write"])

    open_q_weight = weights["open_questions"]
    open_q_score = 0 if blocker_open_questions else open_q_weight
    if blocker_open_questions == 0:
        open_q_score = open_q_weight
    elif blocker_open_questions == 1:
        open_q_score = max(0, open_q_weight // 2)
    else:
        open_q_score = 0

    blocks = {
        "aim_metric": weights["aim_metric"] if has_aim_metric else 0,
        "functional_spec": weights["functional_spec"] if functional_spec_complete else 0,
        "sample": weights["sample"] if has_sample else 0,
        "integrations": integration_score,
        "data_compliance": weights["data_compliance"] if data_compliance_complete else 0,
        "estimate": weights["estimate"] if estimate_complete else 0,
        "business_case": weights["business_case"] if business_case_complete else 0,
        "acceptance": weights["acceptance"] if acceptance_complete else 0,
        "open_questions": open_q_score,
    }
    score = int(sum(blocks.values()))
    bands = cfg["bands"]
    if score < int(bands["not_ready"]):
        band = "not_ready"
    elif score < int(bands["ready_with_assumptions"]):
        band = "ready_with_assumptions"
    else:
        band = "ready_to_build"

    evidence = [f"{name}={value}/{weights.get(name, 18 if name == 'integrations' else 0)}" for name, value in blocks.items()]
    return {
        "score": score,
        "blocks": blocks,
        "band": band,
        "evidence": evidence,
        "inputs": {
            "has_aim_metric": has_aim_metric,
            "functional_spec_complete": functional_spec_complete,
            "has_sample": has_sample,
            "intake_read_available": intake_read_available,
            "system_read_available": system_read_available,
            "system_write_available": system_write_available,
            "data_compliance_complete": data_compliance_complete,
            "estimate_complete": estimate_complete,
            "business_case_complete": business_case_complete,
            "acceptance_complete": acceptance_complete,
            "blocker_open_questions": blocker_open_questions,
        },
    }


def assemble_quality_scores(
    opportunity: dict[str, Any],
    conversation: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    """Bundle the three 0–100 gates with one-line rationales (ES-11)."""
    opp = _score_100(opportunity["score"])
    conv = _score_100(conversation["score"])
    ready = _score_100(readiness["score"])
    return {
        "opportunity_rating": opp,
        "conversation_quality": conv,
        "build_readiness": ready,
        "rationale": {
            "opportunity_rating": _opportunity_line(opportunity, opp),
            "conversation_quality": _conversation_line(conversation, conv),
            "build_readiness": _readiness_line(readiness, ready),
        },
    }


def green_light(
    opportunity_score: int,
    quality_score: int,
    readiness_score: int,
    config: dict[str, Any] | None = None,
) -> bool:
    cfg = config or scoring_config()
    usable = int(cfg["conversation_quality"]["bands"]["usable"])
    ready = int(cfg["build_readiness"]["bands"]["ready_with_assumptions"])
    return opportunity_score >= usable and quality_score >= usable and readiness_score >= ready


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _score_100(value: Any) -> int:
    return max(0, min(100, int(round(float(value)))))


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _opportunity_line(opportunity: dict[str, Any], score: int) -> str:
    inputs = opportunity.get("inputs") or {}
    hours = inputs.get("hours_mo")
    weeks = inputs.get("timeline_weeks")
    hours_bit = f"{hours:g} hours/month" if hours is not None else "named volume"
    weeks_bit = f"{weeks:g}-week path" if weeks is not None else "named timeline"
    return _one_line(f"Opportunity rating {score}/100 from {hours_bit} and a {weeks_bit}.")


def _conversation_line(conversation: dict[str, Any], score: int) -> str:
    band = str(conversation.get("band") or "unscored").replace("_", " ")
    return _one_line(f"Conversation quality {score}/100 ({band}).")


def _readiness_line(readiness: dict[str, Any], score: int) -> str:
    band = str(readiness.get("band") or "unscored").replace("_", " ")
    return _one_line(f"Build-readiness {score}/100 ({band}).")
