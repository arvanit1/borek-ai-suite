"""Deterministic effort estimate. Same inputs → same min/likely/max weeks and tier."""

from __future__ import annotations

from typing import Any

from services.framework.config_loader import estimation_config


def estimate_effort(
    *,
    archetype: str,
    step_count: int,
    system_count: int,
    rule_count: int,
    hard_integration_count: int,
    data_readiness: str,
    reuse: list[str] | None = None,
    builder_count: int = 1,
    declared_likely_weeks: float | None = None,
    declared_build_cost_eur: int | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or estimation_config()
    bases = cfg["base_weeks"]
    if archetype not in bases:
        raise ValueError(f"Unknown archetype '{archetype}'. Use one of: {sorted(bases)}.")

    factors = cfg["factors"]
    readiness_factors = cfg["data_readiness_factor"]
    if data_readiness not in readiness_factors:
        raise ValueError(f"Unknown data_readiness '{data_readiness}'.")

    weeks = float(bases[archetype])
    weeks *= 1 + float(factors["per_step_over_3"]) * max(0, step_count - 3)
    weeks *= 1 + float(factors["per_system_over_1"]) * max(0, system_count - 1)
    weeks += float(factors["per_rule"]) * max(0, rule_count)
    weeks += float(factors["per_hard_integration"]) * max(0, hard_integration_count)
    weeks *= float(readiness_factors[data_readiness])

    discount_pct = 0
    discounts = cfg["reuse_discount_pct"]
    for item in reuse or []:
        discount_pct += int(discounts.get(item, 0))
    discount_pct = min(discount_pct, 40)
    weeks *= 1 - discount_pct / 100

    likely = round(float(declared_likely_weeks), 1) if declared_likely_weeks is not None else round(weeks, 1)
    span = float(cfg["range_pct"]) / 100
    minimum = round(likely * (1 - span), 1)
    maximum = round(likely * (1 + span), 1)
    tier = _tier_for(likely, cfg["tiers"])
    builders = max(1, builder_count)
    build_cost_eur = (
        int(declared_build_cost_eur)
        if declared_build_cost_eur is not None
        else int(round(likely * float(cfg["builder_weekly_rate_eur"]) * builders))
    )

    confidence = {
        "ready": "medium-high",
        "partial": "medium",
        "blockers": "low",
    }[data_readiness]

    return {
        "tier": tier,
        "effort_weeks": {"min": minimum, "likely": likely, "max": maximum},
        "confidence": confidence,
        "team": [f"{builders} builder" + ("" if builders == 1 else "s")],
        "timeline_weeks": likely,
        "build_cost_eur": build_cost_eur,
        "assumptions": [
            f"archetype={archetype}",
            f"data_readiness={data_readiness}",
            f"reuse_discount_pct={discount_pct}",
            f"builder_weekly_rate_eur={cfg['builder_weekly_rate_eur']}",
            *(["likely_effort_weeks declared in conversation"] if declared_likely_weeks is not None else []),
            *(["build_cost_eur declared in conversation"] if declared_build_cost_eur is not None else []),
        ],
        "inputs": {
            "archetype": archetype,
            "step_count": step_count,
            "system_count": system_count,
            "rule_count": rule_count,
            "hard_integration_count": hard_integration_count,
            "data_readiness": data_readiness,
            "reuse": list(reuse or []),
            "builder_count": builders,
        },
    }


def _tier_for(likely_weeks: float, tiers: dict[str, list[float]]) -> str:
    ordered = ("T1", "T2", "T3", "T4")
    for name in ordered:
        low, high = tiers[name]
        if low <= likely_weeks < high:
            return name
    return "T4"
