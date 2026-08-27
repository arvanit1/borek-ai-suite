"""Deterministic business case. Every figure ships its formula and inputs."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from services.framework.config_loader import business_case_config, run_cost_config


def lookup_run_cost_eur_mo(archetype: str, monthly_volume: float, config: dict[str, Any] | None = None) -> int:
    table = (config or run_cost_config())["archetype_volume_lookup"]
    default_archetype = (config or run_cost_config()).get("default_archetype", "doc_extraction")
    bands = table.get(archetype) or table[default_archetype]
    chosen = bands[0][1]
    for threshold, amount in bands:
        if monthly_volume >= threshold:
            chosen = amount
    return int(chosen)


def compute_business_case(
    *,
    automatable_hours_mo: float,
    monthly_volume: float,
    loaded_hourly_cost_eur: float | None = None,
    automation_rate: float | None = None,
    run_cost_eur_mo: int | None = None,
    hours_saved_mo: float | None = None,
    gross_round_to_eur: int | None = None,
    build_cost_eur: int,
    archetype: str,
    qualitative: list[str] | None = None,
    extra_assumptions: list[str] | None = None,
    config: dict[str, Any] | None = None,
    allow_config_defaults: bool = True,
) -> dict[str, Any]:
    cfg = config or business_case_config()
    rate = automation_rate
    if rate is None and allow_config_defaults:
        rate = float(cfg["automation_rate_default"])
    elif rate is None:
        rate = 0.0
    if hours_saved_mo is not None and automatable_hours_mo > 0:
        rate = float(hours_saved_mo) / automatable_hours_mo
    hourly = loaded_hourly_cost_eur
    if hourly is None and allow_config_defaults:
        hourly = float(cfg["loaded_hourly_cost_eur"])
    elif hourly is None:
        hourly = 0.0
    run_cost = int(run_cost_eur_mo if run_cost_eur_mo is not None else lookup_run_cost_eur_mo(archetype, monthly_volume))
    round_to = int(cfg["gross_round_to_eur"] if gross_round_to_eur is None else gross_round_to_eur)
    horizon = int(cfg["roi_horizon_months"])
    payback_decimals = int(cfg["payback_decimals"])

    hours_saved = round(float(hours_saved_mo)) if hours_saved_mo is not None else round(automatable_hours_mo * rate)
    gross_raw = hours_saved * hourly
    gross = int(round(gross_raw / round_to) * round_to) if round_to else int(round(gross_raw))
    net = gross - run_cost
    payback = _round_half_up(build_cost_eur / net, payback_decimals) if net > 0 else None
    roi = round((horizon * net - build_cost_eur) / build_cost_eur * 100) if build_cost_eur else None

    low_rate = float(cfg["sensitivity"]["low_rate"])
    high_rate = float(cfg["sensitivity"]["high_rate"])
    sensitivity = {
        "low": _scenario(automatable_hours_mo, low_rate, hourly, run_cost, build_cost_eur, round_to, payback_decimals, horizon),
        "expected": _scenario(automatable_hours_mo, rate, hourly, run_cost, build_cost_eur, round_to, payback_decimals, horizon),
        "high": _scenario(automatable_hours_mo, high_rate, hourly, run_cost, build_cost_eur, round_to, payback_decimals, horizon),
    }

    assumptions = [
        f"automation_rate={rate}",
        f"loaded_hourly_cost_eur={hourly}",
        f"automatable_hours_mo={automatable_hours_mo}",
        f"run_cost_eur_mo={run_cost}",
        f"build_cost_eur={build_cost_eur}",
        *(extra_assumptions or []),
    ]
    if loaded_hourly_cost_eur is None and allow_config_defaults:
        assumptions.append("loaded_hourly_cost_eur used client default from business_case.config.json")
    elif loaded_hourly_cost_eur is None:
        assumptions.append("loaded_hourly_cost_eur mentioned in conversation but not parsed — gross benefit not computed from config default")

    return {
        "hours_saved_mo": hours_saved,
        "gross_eur_mo": gross,
        "run_cost_eur_mo": run_cost,
        "net_eur_mo": net,
        "payback_months": payback,
        "roi_36m_pct": roi,
        "sensitivity": sensitivity,
        "qualitative": list(qualitative or []),
        "assumptions": assumptions,
        "formulas": {
            "hours_saved_mo": (
                "automatable_hours_mo - customer-declared target remaining hours"
                if hours_saved_mo is not None
                else "round(automatable_hours_mo * automation_rate)"
            ),
            "gross_eur_mo": f"round(hours_saved_mo * loaded_hourly_cost_eur to {round_to} EUR)",
            "net_eur_mo": "gross_eur_mo - run_cost_eur_mo",
            "payback_months": "build_cost_eur / net_eur_mo",
            "roi_36m_pct": "(36 * net_eur_mo - build_cost_eur) / build_cost_eur",
        },
        "inputs": {
            "automatable_hours_mo": automatable_hours_mo,
            "monthly_volume": monthly_volume,
            "automation_rate": rate,
            "loaded_hourly_cost_eur": hourly,
            "build_cost_eur": build_cost_eur,
            "archetype": archetype,
        },
    }


def _round_half_up(value: float, decimals: int) -> float:
    quantize = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantize, rounding=ROUND_HALF_UP))


def _scenario(
    automatable_hours_mo: float,
    rate: float,
    hourly: float,
    run_cost: int,
    build_cost: int,
    round_to: int,
    payback_decimals: int,
    horizon: int,
) -> dict[str, Any]:
    hours = round(automatable_hours_mo * rate)
    gross_raw = hours * hourly
    gross = int(round(gross_raw / round_to) * round_to) if round_to else int(round(gross_raw))
    net = gross - run_cost
    payback = _round_half_up(build_cost / net, payback_decimals) if net > 0 else None
    return {
        "automation_rate": rate,
        "hours_saved_mo": hours,
        "net_eur_mo": net,
        "payback_months": payback,
        "roi_36m_pct": round((horizon * net - build_cost) / build_cost * 100) if build_cost else None,
    }
