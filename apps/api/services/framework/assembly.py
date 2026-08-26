"""Deterministic skeleton: KnowledgeModel buckets → structured FrameworkObject fields."""

from __future__ import annotations

import re
from typing import Any

from services.framework.conflict_resolution import flatten_entries, merge_knowledge_models
from services.knowledge_model.contradictions import detect_contradictions

_VOLUME_RE = re.compile(
    r"(\d[\d,]*)(?:\s+\w+){0,2}\s+(invoices?|cases?|documents?)\s*(?:per|/|a|each)\s*month",
    re.I,
)
_HOURS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\s*/\s*|\s+per\s+)month", re.I)
_EUR_RE = re.compile(r"(?:EUR|€)\s*([\d,.]+)", re.I)
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per\s*cent)", re.I)


def assemble_from_knowledge(
    models: list[dict[str, Any]],
    *,
    opportunity_id: str,
    title_hint: str | None = None,
) -> dict[str, Any]:
    buckets, conflict_items = merge_knowledge_models(models)
    entries = flatten_entries(buckets)
    conflicts: list[dict[str, Any]] = []
    for model in models:
        conflicts.extend(model.get("conflicts") or detect_contradictions(model))
    transcript_ids = [str(model.get("transcript_id", "")) for model in models if model.get("transcript_id")]
    conversation_ids = [str(model.get("conversation_id", "")) for model in models if model.get("conversation_id")]

    systems = _merge_named_systems(
        [_system_from_entry(entry) for entry in buckets.get("named_systems", [])]
    )
    rules = [
        {"name": _short_name(entry["statement"]), "logic": entry["statement"]}
        for entry in buckets.get("named_rules", [])
    ]
    exceptions = [
        {
            "name": _short_name(entry["statement"]),
            "frequency": _first_percent(entry["statement"]) or "named in conversation",
            "handling": entry["statement"],
        }
        for entry in buckets.get("named_exceptions", [])
    ]
    unknowns = [entry["statement"] for entry in buckets.get("unknowns", [])]
    open_items = list(conflict_items)
    for unknown in unknowns:
        open_items.append(
            {
                "description": unknown,
                "item_type": "assumption",
                "owner": "Business",
                "consequence_if_different": "Missing data is never guessed. Confirm before build, or keep as an assumption.",
            }
        )

    numbers = harvest_numbers(entries)
    return {
        "opportunity_id": opportunity_id,
        "title": title_hint or _first_sentence(buckets.get("stated_requirements") or buckets.get("facts") or []) or "Automation opportunity",
        "department": _department(buckets),
        "systems": systems,
        "rules": rules,
        "exceptions": exceptions,
        "access_needs": _access_needs(buckets),
        "open_items": open_items,
        "kpis": _ensure_core_kpis(_kpis(buckets), buckets, numbers),
        "people": [entry["statement"] for entry in buckets.get("people_and_roles", [])],
        "constraints": [entry["statement"] for entry in buckets.get("constraints", [])],
        "risks": [entry["statement"] for entry in buckets.get("risks", [])],
        "facts": [entry["statement"] for entry in buckets.get("facts", [])],
        "requirements": [entry["statement"] for entry in buckets.get("stated_requirements", [])],
        "unknowns": unknowns,
        "transcript_ids": transcript_ids,
        "conversation_ids": conversation_ids,
        "source_entries": entries,
        "conflicts": conflicts,
        "numbers": numbers,
        "engine_inputs": _engine_inputs(entries, systems, rules, numbers),
        "stage3_candidates": _stage3_candidates(buckets),
    }


def harvest_numbers(entries: list[dict[str, Any]]) -> dict[str, Any]:
    blob = " ".join(str(entry.get("statement", "")) for entry in entries)
    volumes = [int(match.group(1).replace(",", "")) for match in _VOLUME_RE.finditer(blob)]
    hours = [float(match.group(1)) for match in _HOURS_RE.finditer(blob)]
    euros = [_parse_amount(match.group(1)) for match in _EUR_RE.finditer(blob)]
    percents = [float(match.group(1)) for match in _PCT_RE.finditer(blob)]
    all_tokens = [_norm_num(token.replace(",", "")) for token in re.findall(r"\d+(?:[.,]\d+)?", blob)]
    return {
        "monthly_volume": volumes[0] if volumes else None,
        "hours_mentions": hours,
        "eur_mentions": euros,
        "percent_mentions": percents,
        "all_tokens": all_tokens,
        "blob": blob,
    }


def allowed_customer_numbers(framework: dict[str, Any]) -> set[str]:
    """Every numeric token that may appear in a customer rendering."""
    allowed: set[str] = set()
    estimate = framework.get("estimate") or {}
    business = framework.get("business_case") or {}
    scores = framework.get("quality_scores") or {}
    for value in (
        estimate.get("build_cost_eur"),
        (estimate.get("effort_weeks") or {}).get("min"),
        (estimate.get("effort_weeks") or {}).get("likely"),
        (estimate.get("effort_weeks") or {}).get("max"),
        business.get("hours_saved_mo"),
        business.get("gross_eur_mo"),
        business.get("run_cost_eur_mo"),
        business.get("net_eur_mo"),
        business.get("payback_months"),
        business.get("roi_36m_pct"),
        scores.get("opportunity_rating"),
        scores.get("conversation_quality"),
        scores.get("build_readiness"),
        (business.get("inputs") or {}).get("automatable_hours_mo"),
        (business.get("inputs") or {}).get("monthly_volume"),
        (business.get("inputs") or {}).get("loaded_hourly_cost_eur"),
        (business.get("inputs") or {}).get("automation_rate"),
    ):
        if value is not None:
            allowed.add(_norm_num(value))
            if isinstance(value, float) and value <= 1:
                allowed.add(_norm_num(value * 100))

    numbers = framework.get("numbers") or {}
    for group in ("hours_mentions", "eur_mentions", "percent_mentions"):
        for item in numbers.get(group) or []:
            allowed.add(_norm_num(item))
    if numbers.get("monthly_volume") is not None:
        allowed.add(_norm_num(numbers["monthly_volume"]))
    for token in numbers.get("all_tokens") or []:
        allowed.add(str(token))
    for token in re.findall(r"\d+(?:[.,]\d+)?", str(numbers.get("blob") or "")):
        allowed.add(_norm_num(token.replace(",", "")))

    for item in framework.get("kpis") or []:
        for field in ("baseline", "target"):
            for token in re.findall(r"\d+(?:[.,]\d+)?", str(item.get(field, ""))):
                allowed.add(_norm_num(token.replace(",", "")))
    return {token for token in allowed if token}


def _engine_inputs(
    entries: list[dict[str, Any]],
    systems: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    numbers: dict[str, Any],
) -> dict[str, Any]:
    hours = _classify_hours(entries)
    automatable = hours["automatable"]
    team_gross = hours["team"]
    volume = numbers.get("monthly_volume")
    has_sample = any("sample" in str(entry.get("statement", "")).lower() for entry in entries)
    write_open = any(
        system.get("status") == "open_dependency" and system.get("direction") in {"write", "read_write"}
        for system in systems
    )
    write_available = any(
        system.get("direction") in {"write", "read_write"} and system.get("status") == "available"
        for system in systems
    )
    return {
        "monthly_volume": volume,
        "automatable_hours_mo": automatable,
        "hours_mo": team_gross or automatable,
        "system_count": max(len(systems), 1),
        "rule_count": len(rules),
        "step_count": max(len(rules) + 2, 4),
        "has_sample": has_sample,
        "write_available": write_available and not write_open,
        "archetype": "system_to_system" if len(systems) >= 2 else "doc_extraction",
        "loaded_hourly_cost_eur": _named_hourly_cost(entries),
        "automation_rate": _named_automation_rate(entries),
    }


def _classify_hours(entries: list[dict[str, Any]]) -> dict[str, float | None]:
    """Current automatable core vs team total vs target remaining — never mix the three."""
    core: list[float] = []
    team: list[float] = []
    current: list[float] = []
    for entry in entries:
        text = str(entry.get("statement") or "")
        for clause in re.split(r"[;,]", text):
            for match in _HOURS_RE.finditer(clause):
                value = float(match.group(1))
                ctx = clause.lower()
                if any(token in ctx for token in ("target", "at most", "remaining", "down to", "reduce to")):
                    continue
                if "automatable" in ctx or "core" in ctx:
                    core.append(value)
                elif "team" in ctx or "whole" in ctx:
                    team.append(value)
                else:
                    current.append(value)
    automatable = max(core) if core else (max(current) if current else None)
    team_hours = max(team) if team else None
    return {"automatable": automatable, "team": team_hours}


def _named_hourly_cost(entries: list[dict[str, Any]]) -> float | None:
    pattern = re.compile(r"(?:EUR|€)\s*([\d,.]+)\s*(?:per|/)\s*h(?:our)?", re.I)
    for entry in entries:
        match = pattern.search(str(entry.get("statement") or ""))
        if match:
            return _parse_amount(match.group(1))
    return None


def _named_automation_rate(entries: list[dict[str, Any]]) -> float | None:
    percents: list[float] = []
    for entry in entries:
        text = str(entry.get("statement") or "")
        lower = text.lower()
        if "auto-match" not in lower and "automatch" not in lower:
            continue
        percents.extend(float(match.group(1)) for match in _PCT_RE.finditer(text))
    named = [value for value in percents if value > 0]
    if not named:
        return None
    rate = max(named)
    return rate / 100 if rate > 1 else rate


def _system_key(text: str) -> str:
    lower = text.lower()
    if "mailbox" in lower or "outlook" in lower or "graph" in lower:
        return "mailbox"
    if "erp" in lower:
        return "erp"
    if "ocr" in lower:
        return "ocr"
    if "exception" in lower or "approval application" in lower or "approval app" in lower:
        return "exception_app"
    return f"named:{_short_name(text).lower()}"


def _merge_direction(left: str, right: str) -> str:
    pair = {left, right}
    if "read_write" in pair or pair == {"read", "write"}:
        return "read_write"
    if "write" in pair:
        return "write"
    if "read" in pair:
        return "read"
    return left or right or "internal"


def _merge_named_systems(systems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per named business system. Graph/REST stay access paths, not extra systems."""
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in systems:
        key = _system_key(" ".join(str(item.get(field) or "") for field in ("name", "access_path", "role")))
        if key not in grouped:
            grouped[key] = dict(item)
            order.append(key)
            continue
        existing = grouped[key]
        existing["direction"] = _merge_direction(str(existing.get("direction") or ""), str(item.get("direction") or ""))
        existing["access_path"] = _join_unique(str(existing.get("access_path") or ""), str(item.get("access_path") or ""))
        if item.get("status") == "open_dependency":
            existing["status"] = "open_dependency"
        if item.get("direction") in {"write", "read_write"}:
            existing["role"] = item.get("role") or existing.get("role")
        name = str(item.get("name") or "")
        if name and len(name) < len(str(existing.get("name") or "")):
            existing["name"] = name
    return [grouped[key] for key in order]


def _join_unique(left: str, right: str) -> str:
    parts: list[str] = []
    for item in (left, right):
        text = item.strip()
        if text and text not in parts:
            parts.append(text)
    return " ".join(parts)


def _system_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    text = entry["statement"]
    lower = text.lower()
    if "mailbox" in lower or "outlook" in lower or "graph" in lower:
        direction = "read"
        role = "Source of invoices or intake documents"
    elif "write" in lower or "posting" in lower:
        direction = "write"
        role = "Posting / write-back"
    elif "erp" in lower:
        direction = "read"
        role = "System of record"
    else:
        direction = "internal"
        role = text
    status = "open_dependency" if any(word in lower for word in ("open", "pending", "approval", "not yet")) else "available"
    classification = "Confidential" if "confidential" in lower else "as reported"
    return {
        "name": _short_name(text),
        "role": role,
        "direction": direction if direction in {"read", "write", "read_write", "internal"} else "internal",
        "access_path": text,
        "data_classification": classification,
        "status": status,
    }


def _access_needs(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    needs: list[dict[str, Any]] = []
    seen: set[str] = set()
    category_map = (
        ("read", "Read access"),
        ("write", "Write access"),
        ("sandbox", "Test data / sandbox"),
        ("sample", "Sample documents"),
        ("rule", "Rule confirmation"),
        ("sso", "Identity / SSO"),
        ("approval", "Access approval"),
    )
    for entry in buckets.get("constraints", []) + buckets.get("stated_requirements", []):
        text = entry["statement"]
        lower = text.lower()
        for needle, category in category_map:
            if needle in lower and category.lower() not in seen:
                seen.add(category.lower())
                needs.append(
                    {
                        "category": category,
                        "detail": text,
                        "status": "named in conversation",
                        "owner": "IT" if needle in {"read", "write", "sso", "sandbox"} else "Business",
                    }
                )
    if not needs:
        for entry in buckets.get("constraints", []) + buckets.get("stated_requirements", []):
            text = entry["statement"]
            if any(word in text.lower() for word in ("access", "api", "sandbox", "sample", "approval")):
                needs.append(
                    {
                        "category": _short_name(text),
                        "detail": text,
                        "status": "named in conversation",
                        "owner": "IT" if "it" in text.lower() or "api" in text.lower() else "Business",
                    }
                )
    _ensure_access_categories(needs)
    return needs


def _ensure_access_categories(needs: list[dict[str, Any]]) -> None:
    """ES-21 — cover read, write, sample/test, rule confirmation, identity even when only partially named."""
    required = (
        ("Read access", "read"),
        ("Write access", "write"),
        ("Sample / test data", "sample"),
        ("Rule confirmation", "rule"),
        ("Identity / SSO", "identity"),
    )
    blob = " ".join(str(item.get("category", "")).lower() for item in needs)
    for category, token in required:
        if token in blob:
            continue
        needs.append(
            {
                "category": category,
                "detail": "Not named in the conversations. Recorded as an open item rather than guessed.",
                "status": "open",
                "owner": "Business",
            }
        )


def _ensure_core_kpis(
    kpis: list[dict[str, Any]],
    buckets: dict[str, list[dict[str, Any]]],
    numbers: dict[str, Any],
) -> list[dict[str, Any]]:
    """ES-17 — ensure automation, manual time, quality/error, and cycle-time KPI categories exist."""
    open_item = "Not named in the conversations. Recorded as an open item rather than guessed."
    merged = list(kpis)
    names = " ".join(str(item.get("name", "")).lower() for item in merged)

    def add(name: str, baseline: str, target: str, measured_via: str) -> None:
        nonlocal names
        if name.lower() in names:
            return
        merged.append(
            {
                "name": name,
                "baseline": baseline,
                "target": target,
                "measured_via": measured_via,
            }
        )
        names = f"{names} {name.lower()}"

    if not any(token in names for token in ("automation", "auto-match", "auto match")):
        add(
            "Automation rate",
            open_item,
            open_item,
            "agent statistics per case",
        )
    if not any(token in names for token in ("manual", "handling time", "hours")):
        hours = (numbers.get("hours_mentions") or [None])[0]
        baseline = f"{hours} hours/month" if hours else open_item
        add("Manual handling time", baseline, open_item, "exception-queue time tracking")
    if not any(token in names for token in ("quality", "error", "wrong", "success")):
        add("Quality / error rate", open_item, open_item, "audit log and spot checks")
    if not any(token in names for token in ("cycle", "lead time", "close", "month-end")):
        add("Cycle time", open_item, open_item, "process timestamps / month-end tracking")
    return merged


def _kpis(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    kpis: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?P<name>.+?)\s*baseline\s+(?P<baseline>.+?),\s*target\s+(?P<target>.+?),\s*measured via\s+(?P<via>.+)$",
        re.I,
    )
    for entry in buckets.get("stated_requirements", []) + buckets.get("facts", []):
        text = entry["statement"]
        if not any(word in text.lower() for word in ("kpi", "target", "baseline", "auto-match", "success")):
            continue
        match = pattern.search(text)
        if match:
            name = match.group("name")
            name = re.sub(r"^KPI\s+", "", name, flags=re.I).strip(" :")
            kpis.append(
                {
                    "name": name,
                    "baseline": match.group("baseline").strip(),
                    "target": match.group("target").strip(),
                    "measured_via": match.group("via").strip().rstrip("."),
                }
            )
        else:
            kpis.append(
                {
                    "name": _short_name(text),
                    "baseline": "as named in the conversation",
                    "target": text,
                    "measured_via": "as named in the conversation",
                }
            )
    return kpis


def _stage3_candidates(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for entry in buckets.get("named_exceptions", []) + buckets.get("facts", []):
        text = entry["statement"]
        if any(word in text.lower() for word in ("later", "stage 3", "credit note", "email", "handoff", "out of scope")):
            refs = entry.get("source_refs") or []
            pointer = ""
            if refs:
                pointer = f"{refs[0].get('conversation_id')}:{refs[0].get('excerpt_pointer')}"
            if pointer:
                candidates.append({"description": text, "source_ref": pointer})
    return candidates


def _department(buckets: dict[str, list[dict[str, Any]]]) -> str:
    for entry in buckets.get("people_and_roles", []) + buckets.get("facts", []):
        text = entry["statement"]
        for label in ("Finance", "Accounts Payable", "AP", "Procurement", "HR", "Operations"):
            if label.lower() in text.lower():
                return label
    return "Unspecified"


def _first_sentence(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return ""
    return entries[0]["statement"]


def _short_name(text: str) -> str:
    clipped = text.split(".")[0].strip()
    for separator in (":", " — ", " - "):
        if separator in clipped:
            clipped = clipped.split(separator)[0].strip()
            break
    if len(clipped) > 48:
        clipped = clipped[:48].rsplit(" ", 1)[0]
    return clipped or text[:48]


def _first_percent(text: str) -> str | None:
    match = _PCT_RE.search(text)
    return f"{match.group(1)} %" if match else None


def _parse_amount(raw: str) -> float:
    cleaned = raw.replace(".", "").replace(",", ".") if raw.count(",") == 1 and raw.count(".") > 1 else raw.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _norm_num(value: Any) -> str:
    try:
        number = float(str(value).replace(",", ""))
    except ValueError:
        return str(value)
    if number.is_integer():
        return str(int(number))
    return str(number)
