"""Deterministic skeleton: KnowledgeModel buckets → structured FrameworkObject fields."""

from __future__ import annotations

import re
from typing import Any

from services.framework.conflict_resolution import flatten_entries, merge_knowledge_models
from services.knowledge_model.contradictions import detect_contradictions

_VOLUME_RE = re.compile(
    r"(\d[\d,]*)(?:\s+\w+){0,2}\s+"
    r"(invoices?|cases?|documents?|requisitions?|requests?|orders?|transactions?)\s*"
    r"(?:per|/|a|each)\s*month",
    re.I,
)
_VOLUME_NOUNS = r"(?:invoices?|cases?|documents?|requisitions?|requests?|orders?|transactions?|tickets?|units?|rmas?|hires?|batches?)"
_VOLUME_LOOSE_RE = re.compile(
    rf"(?:(?:monthly\s+)?volume\s+(?:is|of|about|roughly|approximately)?\s*|"
    rf"(?:process(?:es)?|handle(?:s)?|about|roughly|approximately)\s+)"
    rf"(\d[\d,]*)\s+(?:\w+\s+){{0,3}}{_VOLUME_NOUNS}",
    re.I,
)
_VOLUME_MONTHLY_RE = re.compile(
    rf"(\d[\d,]*)\s+(?:\w+\s+){{0,3}}{_VOLUME_NOUNS}\b",
    re.I,
)
_HOURS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\s*/\s*|\s+(?:per|a|each)\s+)month",
    re.I,
)
_HOURS_LOOSE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:staff-)?h(?:ours?)?(?:\s+(?:per|/|each|a)\s*month|\s+(?:on|in|for)\b|\s+monthly\b|\s+each month)",
    re.I,
)
_EUROS_PER_HOUR_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s+euros?\s+(?:an?\s+)?h(?:our)?|"
    r"(?:EUR|€)\s*([\d,.]+)\s*(?:per|/)\s*h(?:our)?|"
    r"(?:EUR|€)\s*([\d,.]+)\s+per hour",
    re.I,
)
_EUR_RE = re.compile(r"(?:EUR|€)\s*([\d,.]+)", re.I)
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per\s*cent)", re.I)
_BUILD_WEEKS_RE = re.compile(r"(?:estimated|estimate|build)[^.]{0,80}?(\d+(?:\.\d+)?)\s+weeks?", re.I)
_BUILD_WEEKS_WORD_RE = re.compile(
    r"(?:estimated|estimate|build)[^.]{0,80}?\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+weeks?",
    re.I,
)
_HOURS_TARGET_CONNECTOR = r"(?:\bto\b|at\s+most|no\s+more\s+than)"
_HOURS_AFTER_CONNECTOR = (
    r"(?:(?:(?:under|below)|less\s+than)\s+(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?))\s+hours?"
)
_TARGET_REMAINING_HOURS_RE = re.compile(
    r"(?:reduce|lower|cut(?:ting)?)[^.]{0,100}?"
    rf"{_HOURS_TARGET_CONNECTOR}\s*{_HOURS_AFTER_CONNECTOR}(?:\s+each|\s+per|\s*/)?\s*month",
    re.I,
)
_REDUCTION_HOURS_RE = re.compile(
    r"(?:reduce|lower|cut(?:ting)?)[^.]{0,100}?\bfrom\s*(\d+(?:\.\d+)?)\s+hours?[^.]{0,100}?"
    rf"{_HOURS_TARGET_CONNECTOR}\s*{_HOURS_AFTER_CONNECTOR}",
    re.I,
)
_NUMBER_WORDS = {
    "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0,
    "five": 5.0, "six": 6.0, "seven": 7.0, "eight": 8.0,
    "nine": 9.0, "ten": 10.0, "eleven": 11.0, "twelve": 12.0,
}


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
    engine_inputs, engine_open_items = build_engine_inputs(entries, systems, rules, numbers)
    open_items.extend(engine_open_items)
    return {
        "opportunity_id": opportunity_id,
        "title": title_hint or _first_sentence(buckets.get("stated_requirements") or buckets.get("facts") or []) or "Automation opportunity",
        "department": _department(buckets),
        "systems": systems,
        "rules": rules,
        "exceptions": exceptions,
        "access_needs": _access_needs(buckets),
        "open_items": open_items,
        "kpis": _ensure_core_kpis(_kpis(buckets), buckets, numbers, engine_inputs),
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
        "engine_inputs": engine_inputs,
        "stage3_candidates": _stage3_candidates(buckets),
    }


def harvest_numbers(entries: list[dict[str, Any]]) -> dict[str, Any]:
    blob = " ".join(str(entry.get("statement", "")) for entry in entries)
    volumes = [int(match.group(1).replace(",", "")) for match in _VOLUME_RE.finditer(blob)]
    if not volumes:
        for entry in entries:
            volume = _volume_from_statement(str(entry.get("statement") or ""))
            if volume is not None:
                volumes.append(volume)
    hours = [float(match.group(1)) for match in _HOURS_RE.finditer(blob)]
    if not hours:
        for entry in entries:
            value = _hours_from_statement(str(entry.get("statement") or ""))
            if value is not None:
                hours.append(value)
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
    for root in (
        framework.get("estimate"),
        framework.get("business_case"),
        framework.get("quality_scores"),
        framework.get("assessments"),
        framework.get("numbers"),
    ):
        _register_numeric_tree(allowed, root)

    business = framework.get("business_case") or {}
    inputs = business.get("inputs") or {}
    current_hours = inputs.get("automatable_hours_mo") or inputs.get("hours_mo")
    hourly_cost = inputs.get("loaded_hourly_cost_eur")
    if current_hours is not None and hourly_cost is not None:
        _register_numeric_variants(allowed, float(current_hours) * float(hourly_cost))

    hours_saved = business.get("hours_saved_mo")
    if hours_saved is not None and current_hours is not None and float(current_hours) > 0:
        _register_numeric_variants(allowed, float(hours_saved) / float(current_hours))

    for item in framework.get("kpis") or []:
        for field in ("baseline", "target"):
            for token in re.findall(r"\d+(?:[.,]\d+)?", str(item.get(field, ""))):
                _register_numeric_variants(allowed, token.replace(",", ""))
    entry_count = len(framework.get("source_entries") or [])
    if entry_count:
        _register_numeric_variants(allowed, entry_count)
    return {token for token in allowed if token}


def _register_numeric_tree(allowed: set[str], value: Any) -> None:
    if value is None:
        return
    if isinstance(value, dict):
        for item in value.values():
            _register_numeric_tree(allowed, item)
        return
    if isinstance(value, list):
        for item in value:
            _register_numeric_tree(allowed, item)
        return
    if isinstance(value, (int, float)):
        _register_numeric_variants(allowed, value)
        return
    if isinstance(value, str):
        for token in re.findall(r"\d+(?:[.,]\d+)?", value.replace(",", "")):
            _register_numeric_variants(allowed, token)
        return
    _register_numeric_variants(allowed, value)


def _register_numeric_variants(allowed: set[str], value: Any) -> None:
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        text = str(value).strip()
        if text:
            allowed.add(text)
        return
    forms = {number, round(number, 2), round(number, 1), int(round(number))}
    if abs(number - int(round(number))) < 1e-9:
        whole = int(round(number))
        forms.add(whole)
        if whole >= 1000:
            allowed.add(f"{whole:,}")
    for item in forms:
        if isinstance(item, float) and item.is_integer():
            allowed.add(str(int(item)))
        else:
            allowed.add(_norm_num(item))
    if 0 < number <= 1:
        pct = number * 100
        for item in (pct, round(pct, 1), round(pct, 2), int(round(pct))):
            allowed.add(_norm_num(item))


_FINANCIAL_METRIC_KINDS = frozenset(
    {
        "monthly_volume",
        "automatable_hours_mo",
        "team_hours_mo",
        "target_remaining_hours_mo",
        "loaded_hourly_cost_eur",
        "automation_rate",
        "exception_rate_pct",
    }
)


def build_engine_inputs(
    entries: list[dict[str, Any]],
    systems: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    numbers: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Harvest engine inputs: typed metric fields first (ES-5), regex-on-statement second."""
    hours = _classify_hours(entries)
    merged = {
        "monthly_volume": _harvest_financial_value(entries, "monthly_volume", _volume_from_statement),
        "automatable_hours_mo": _harvest_metric_only(entries, "automatable_hours_mo") or hours["automatable"],
        "team_hours_mo": _harvest_metric_only(entries, "team_hours_mo") or hours["team"],
        "loaded_hourly_cost_eur": _harvest_financial_value(
            entries, "loaded_hourly_cost_eur", _hourly_cost_from_statement
        ),
        "automation_rate": _harvest_financial_value(
            entries, "automation_rate", _automation_rate_from_statement
        ),
        "target_remaining_hours_mo": _harvest_financial_value(
            entries, "target_remaining_hours_mo", _target_remaining_hours_from_statement
        ),
        "run_cost_eur_mo": _harvest_declared_cost(
            entries, markers=("run cost", "monthly run cost", "monthly service cost")
        ),
        "build_cost_eur": _harvest_declared_cost(
            entries, markers=("build budget", "build cost", "initial build")
        ),
        "declared_effort_weeks": _harvest_declared_effort_weeks(entries),
    }
    unresolved = _unresolved_engine_fields(entries, merged)
    open_items = _engine_input_gap_open_items(entries, merged, unresolved)
    open_items.extend(_ai_inferred_financial_open_items(entries))

    has_sample = any("sample" in str(entry.get("statement", "")).lower() for entry in entries)
    write_open = any(
        system.get("status") == "open_dependency" and system.get("direction") in {"write", "read_write"}
        for system in systems
    )
    write_available = any(
        system.get("direction") in {"write", "read_write"} and system.get("status") == "available"
        for system in systems
    )
    inputs = {
        "monthly_volume": merged.get("monthly_volume"),
        "automatable_hours_mo": merged.get("automatable_hours_mo"),
        "hours_mo": merged.get("team_hours_mo") or merged.get("automatable_hours_mo"),
        "system_count": max(len(systems), 1),
        "rule_count": len(rules),
        "step_count": max(len(rules) + 2, 4),
        "has_sample": has_sample,
        "write_available": write_available and not write_open,
        "archetype": "system_to_system" if len(systems) >= 2 else "doc_extraction",
        "loaded_hourly_cost_eur": merged.get("loaded_hourly_cost_eur"),
        "automation_rate": merged.get("automation_rate"),
        "run_cost_eur_mo": merged.get("run_cost_eur_mo"),
        "build_cost_eur": merged.get("build_cost_eur"),
        "declared_effort_weeks": merged.get("declared_effort_weeks"),
        "target_remaining_hours_mo": merged.get("target_remaining_hours_mo"),
        "qualitative": _qualitative_benefits(entries),
        "unresolved_fields": sorted(unresolved),
    }
    return inputs, open_items


def _engine_inputs(
    entries: list[dict[str, Any]],
    systems: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    numbers: dict[str, Any],
) -> dict[str, Any]:
    inputs, _open_items = build_engine_inputs(entries, systems, rules, numbers)
    return inputs


def _entry_usable_for_financial(entry: dict[str, Any]) -> bool:
    """ES-7 — only high-confidence SOURCE_FACT or USER_INPUT may feed Ch.9 calculations."""
    if not entry.get("source_refs"):
        return False
    origin = str(entry.get("origin") or "").strip()
    confidence = str(entry.get("confidence") or "").strip()
    if origin in {"AI_INFERENCE", "OPEN_QUESTION"}:
        return False
    if origin == "USER_INPUT":
        return confidence == "high"
    if origin == "SOURCE_FACT":
        return confidence == "high"
    return False


def _entries_financial_priority(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda entry: (
            0 if _entry_usable_for_financial(entry) else 1,
            0 if entry.get("metric") else 1,
            str(entry.get("statement", "")),
        ),
    )


def _harvest_metric_only(entries: list[dict[str, Any]], metric_kind: str) -> Any:
    for entry in _entries_financial_priority(entries):
        if not _entry_usable_for_financial(entry):
            continue
        metric = entry.get("metric") or {}
        if metric.get("value") is None:
            continue
        if _metric_matches_kind(entry, metric_kind):
            return _coerce_metric_value(metric_kind, metric["value"])
    return None


def _metric_matches_kind(entry: dict[str, Any], metric_kind: str) -> bool:
    metric = entry.get("metric") or {}
    kind = str(metric.get("kind") or "")
    if kind == metric_kind:
        return True
    if metric_kind == "automatable_hours_mo" and kind == "team_hours_mo":
        return _statement_is_automatable_scope(str(entry.get("statement") or ""))
    return False


def _harvest_financial_value(
    entries: list[dict[str, Any]],
    metric_kind: str,
    extract: Any,
) -> Any:
    for entry in _entries_financial_priority(entries):
        if not _entry_usable_for_financial(entry):
            continue
        metric = entry.get("metric") or {}
        if metric.get("value") is not None and _metric_matches_kind(entry, metric_kind):
            return _coerce_metric_value(metric_kind, metric["value"])
    for entry in _entries_financial_priority(entries):
        if not _entry_usable_for_financial(entry):
            continue
        value = extract(str(entry.get("statement") or ""))
        if value is not None:
            return value
    return None


def _harvest_declared_cost(entries: list[dict[str, Any]], *, markers: tuple[str, ...]) -> int | None:
    for entry in _entries_financial_priority(entries):
        if not _entry_usable_for_financial(entry):
            continue
        value = _cost_from_statement(str(entry.get("statement") or ""), markers=markers)
        if value is not None:
            return value
    return None


def _coerce_metric_value(kind: str, raw: Any) -> Any:
    number = float(raw)
    if kind in {"monthly_volume", "run_cost_eur_mo", "build_cost_eur"}:
        return int(round(number))
    if kind == "loaded_hourly_cost_eur":
        return float(number)
    if kind == "automation_rate":
        return number / 100 if number > 1 else number
    return number


def _ai_inferred_financial_open_items(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in entries:
        origin = str(entry.get("origin") or "")
        confidence = str(entry.get("confidence") or "")
        if origin == "AI_INFERENCE":
            pass
        elif origin == "SOURCE_FACT" and confidence == "low" and _looks_like_estimate(str(entry.get("statement") or "")):
            pass
        else:
            continue
        statement = str(entry.get("statement") or "")
        metric = entry.get("metric") or {}
        has_financial_signal = metric.get("kind") in _FINANCIAL_METRIC_KINDS or any(
            (
                _mentions_volume_for_engine(statement),
                _mentions_automatable_hours(statement),
                _mentions_hourly_cost(statement),
                _mentions_hour_target(statement),
                _mentions_automation_rate(statement),
                bool(_PCT_RE.search(statement) and re.search(r"(?:hour|cost|volume|case|ticket|unit|hire|invoice|percent)", statement, re.I)),
            )
        )
        if not has_financial_signal:
            continue
        label = (
            "Low-confidence estimate needs confirmation before it can feed the business case"
            if origin == "SOURCE_FACT"
            else "AI-inferred financial figure needs confirmation before it can feed the business case"
        )
        items.append(
            {
                "description": f"{label} ({_short_name(statement)}).",
                "item_type": "assumption",
                "owner": "Business",
                "consequence_if_different": (
                    "AI-inferred numbers are never merged with client-stated figures. Confirm against the conversation."
                ),
            }
        )
    return items


def _harvest_declared_effort_weeks(entries: list[dict[str, Any]]) -> float | None:
    for entry in _entries_financial_priority(entries):
        if not _entry_usable_for_financial(entry):
            continue
        value = _effort_weeks_from_statement(str(entry.get("statement") or ""))
        if value is not None:
            return value
    return None


def _has_source_refs(entry: dict[str, Any]) -> bool:
    return bool(entry.get("source_refs"))


def _volume_from_statement(text: str) -> int | None:
    match = _VOLUME_RE.search(text)
    if match:
        return int(match.group(1).replace(",", ""))
    loose = _VOLUME_LOOSE_RE.search(text)
    if loose:
        return int(loose.group(1).replace(",", ""))
    if re.search(r"(?:per|/|each|a)\s*month|monthly|each month|every four weeks", text, re.I):
        monthly = _VOLUME_MONTHLY_RE.search(text)
        if monthly:
            return int(monthly.group(1).replace(",", ""))
        every_weeks = re.search(
            rf"(\d[\d,]*)\s+(?:\w+\s+){{0,3}}{_VOLUME_NOUNS}[^.]*?\bevery four weeks\b",
            text,
            re.I,
        )
        if every_weeks:
            return int(every_weeks.group(1).replace(",", ""))
        about_month = re.search(rf"(?:about|roughly)\s+(\d[\d,]*)\s+a month\b", text, re.I)
        if about_month and re.search(_VOLUME_NOUNS, text, re.I):
            return int(about_month.group(1).replace(",", ""))
    return None


def _hourly_cost_from_statement(text: str) -> float | None:
    match = _EUROS_PER_HOUR_RE.search(text)
    if match:
        for group in match.groups():
            if group is not None:
                return _parse_amount(group)
    if re.search(r"(?:loaded cost|hourly cost|cost per hour|loaded for your business case)", text, re.I):
        match = _EUR_RE.search(text)
        if match:
            return _parse_amount(match.group(1))
    return None


def _automation_rate_from_statement(text: str) -> float | None:
    lower = text.lower()
    if not any(token in lower for token in ("auto-match", "automatch", "automation rate", "automation-rate")):
        return None
    percents = [float(match.group(1)) for match in _PCT_RE.finditer(text)]
    named = [value for value in percents if value > 0]
    if not named:
        return None
    rate = max(named)
    return rate / 100 if rate > 1 else rate


def _cost_from_statement(text: str, *, markers: tuple[str, ...]) -> int | None:
    if not any(marker in text.lower() for marker in markers):
        return None
    match = _EUR_RE.search(text)
    if match:
        return int(_parse_amount(match.group(1)))
    return None


def _effort_weeks_from_statement(text: str) -> float | None:
    match = _BUILD_WEEKS_RE.search(text)
    if match:
        return float(match.group(1))
    word_match = _BUILD_WEEKS_WORD_RE.search(text)
    if word_match:
        return _NUMBER_WORDS[word_match.group(1).lower()]
    return None


def _target_remaining_hours_from_statement(text: str) -> float | None:
    match = _TARGET_REMAINING_HOURS_RE.search(text)
    if match:
        return _hour_target_from_match(match, start=1)
    reduction = _REDUCTION_HOURS_RE.search(text)
    if reduction:
        return _hour_target_from_match(reduction, start=2)
    capped = re.search(
        r"(?:capped at|under|below|down to|target state is)\s+(\d+(?:\.\d+)?)\s*(?:staff-)?h(?:ours?)?",
        text,
        re.I,
    )
    if capped:
        return float(capped.group(1))
    touch = re.search(r"(\d+(?:\.\d+)?)\s+h(?:ours?)?\s+of human touch", text, re.I)
    if touch:
        return float(touch.group(1))
    return None


def _hours_from_statement(text: str) -> float | None:
    match = _HOURS_RE.search(text)
    if match:
        return float(match.group(1))
    loose = _HOURS_LOOSE_RE.search(text)
    if loose:
        return float(loose.group(1))
    return None


def _unresolved_engine_fields(entries: list[dict[str, Any]], merged: dict[str, Any]) -> set[str]:
    unresolved: set[str] = set()
    checks = (
        ("monthly_volume", _mentions_volume_for_engine),
        ("automatable_hours_mo", _mentions_automatable_hours),
        ("loaded_hourly_cost_eur", _mentions_hourly_cost),
        ("target_remaining_hours_mo", _mentions_hour_target),
        ("automation_rate", _mentions_automation_rate),
    )
    for field, mention_fn in checks:
        if merged.get(field) is not None:
            continue
        if any(_entry_usable_for_financial(entry) and mention_fn(str(entry.get("statement") or "")) for entry in entries):
            unresolved.add(field)
    return unresolved


def _engine_input_gap_open_items(
    entries: list[dict[str, Any]],
    merged: dict[str, Any],
    unresolved: set[str],
) -> list[dict[str, Any]]:
    labels = {
        "monthly_volume": "Monthly volume",
        "automatable_hours_mo": "Automatable hours",
        "loaded_hourly_cost_eur": "Loaded hourly cost",
        "target_remaining_hours_mo": "Target remaining hours",
        "automation_rate": "Automation rate",
    }
    items: list[dict[str, Any]] = []
    for field in sorted(unresolved):
        for entry in entries:
            if not _entry_usable_for_financial(entry):
                continue
            statement = str(entry.get("statement") or "")
            if field == "monthly_volume" and not _mentions_volume_for_engine(statement):
                continue
            if field == "automatable_hours_mo" and (
                not _mentions_automatable_hours(statement) or _statement_is_hour_target_only(statement)
            ):
                continue
            if field == "loaded_hourly_cost_eur" and not _mentions_hourly_cost(statement):
                continue
            if field == "target_remaining_hours_mo" and not _mentions_hour_target(statement):
                continue
            if field == "automation_rate" and not _mentions_automation_rate(statement):
                continue
            if merged.get(field) is not None:
                continue
            items.append(
                {
                    "description": (
                        f"{labels[field]} mentioned in conversation but not parsed into engine_inputs — "
                        f"needs owner review ({_short_name(statement)})."
                    ),
                    "item_type": "assumption",
                    "owner": "Business",
                    "consequence_if_different": (
                        "Missing information is never guessed. Confirm the figure before it is used in the business case."
                    ),
                }
            )
            break
    return items


def _mentions_volume_for_engine(text: str) -> bool:
    lower = text.lower()
    return bool(
        _volume_from_statement(text)
        or (
            re.search(_VOLUME_NOUNS, lower)
            and re.search(r"(?:per|/|each|a)\s*month|monthly|each month|\bvolume\b", lower)
            and re.search(r"\d", text)
        )
    )


def _mentions_automatable_hours(text: str) -> bool:
    lower = text.lower()
    if not _hours_from_statement(text):
        return False
    if _statement_is_hour_target_only(text):
        return False
    return _statement_is_automatable_scope(text) or any(
        token in lower
        for token in ("hour", "manual", "core", "repeatable", "automatable", "checking", "effort", "spend", "burn", "log")
    )


_AUTOMATABLE_SCOPE_TOKENS = (
    "automatable",
    "matchable",
    "repeatable",
    "tier-one",
    "tier one",
    "core work",
    "manual checking",
    "inspection",
    "relabeling",
    "labor hours",
    "staff-hours",
    "review work",
    "paperwork",
)


def _statement_is_automatable_scope(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in _AUTOMATABLE_SCOPE_TOKENS)


def _statement_is_hour_target_only(text: str) -> bool:
    lower = text.lower()
    if not _mentions_hour_target(text):
        return False
    return not _statement_is_automatable_scope(text) and not any(
        token in lower for token in ("spend", "burn", "log", "require", "takes", "currently", "today")
    )


def _looks_like_estimate(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in ("gut", "guess", "maybe", "hypothesis", "optimistic", "could reach", "sounds plausible"))


def _mentions_hourly_cost(text: str) -> bool:
    lower = text.lower()
    if _hourly_cost_from_statement(text) is not None:
        return True
    return bool(
        re.search(r"(?:loaded|hourly|staff)\s+(?:cost|rate)", lower)
        and re.search(r"(?:per|/|\ban?\s+)h(?:our)?|per hour|an hour", lower)
    )


def _mentions_hour_target(text: str) -> bool:
    lower = text.lower()
    return bool(
        _target_remaining_hours_from_statement(text)
        or (
            re.search(r"(?:reduce|cut|lower|target|under|below|less than)", lower)
            and re.search(r"\d+(?:\.\d+)?\s*h(?:ours?)?", lower)
        )
    )


def _mentions_automation_rate(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in ("auto-match", "automatch", "automation rate", "automation-rate")) and bool(_PCT_RE.search(text))


def _classify_hours(entries: list[dict[str, Any]]) -> dict[str, float | None]:
    """Current automatable core vs team total vs target remaining — never mix the three."""
    core: list[float] = []
    team: list[float] = []
    current: list[float] = []
    for entry in _entries_financial_priority(entries):
        if not _entry_usable_for_financial(entry):
            continue
        text = str(entry.get("statement") or "")
        for match in _REDUCTION_HOURS_RE.finditer(text):
            core.append(float(match.group(1)))
        for clause in re.split(r"[;,]", text):
            match = _hours_from_statement(clause)
            if match is None:
                continue
            value = float(match)
            ctx = clause.lower()
            if any(token in ctx for token in ("target", "at most", "remaining", "down to", "reduce to", "under", "below", "less than", "capped at")):
                continue
            if _statement_is_automatable_scope(clause):
                core.append(value)
            elif "team" in ctx or "whole" in ctx:
                team.append(value)
            else:
                current.append(value)
    automatable = max(core) if core else (max(current) if current else None)
    team_hours = max(team) if team else None
    return {"automatable": automatable, "team": team_hours}


def _hour_target_from_match(match: re.Match[str], *, start: int) -> float:
    for idx in (start, start + 1):
        value = match.group(idx)
        if value is not None:
            return float(value)
    raise ValueError("hour target capture missing")


def _qualitative_benefits(entries: list[dict[str, Any]]) -> list[str]:
    """Keep ES-23 qualitative benefits grounded in the customer conversation."""
    benefits: list[str] = []
    for entry in entries:
        text = str(entry.get("statement") or "")
        lower = text.lower()
        if "month end" in lower or "backlog" in lower:
            if "expense" in lower:
                benefits.append("Faster month-end close by reducing the expense-report backlog.")
            elif "requisition" in lower or "procurement" in lower:
                benefits.append("Faster month-end close by reducing the requisition backlog.")
            else:
                benefits.append("Faster month-end close by reducing the processing backlog.")
        elif any(token in lower for token in ("focus on exceptions", "firefight", "policy improvement")):
            benefits.append(
                "Analysts can focus on exceptions and policy improvement rather than firefighting."
            )
    return list(dict.fromkeys(benefits))


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
    engine_inputs: dict[str, Any] | None = None,
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
        current_hours = None
        if engine_inputs:
            current_hours = engine_inputs.get("automatable_hours_mo") or engine_inputs.get("hours_mo")
        if current_hours is None:
            current_hours = (numbers.get("hours_mentions") or [None])[0]
        baseline = f"{current_hours:g} hours/month" if current_hours else open_item
        target = open_item
        if engine_inputs and engine_inputs.get("target_remaining_hours_mo") is not None:
            target = f"{engine_inputs['target_remaining_hours_mo']:g} hours/month"
        add("Manual handling time", baseline, target, "exception-queue time tracking")
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
        if any(
            word in text.lower()
            for word in ("later", "stage 3", "credit note", "handoff", "out of scope")
        ):
            refs = entry.get("source_refs") or []
            pointer = ""
            if refs:
                pointer = f"{refs[0].get('conversation_id')}:{refs[0].get('excerpt_pointer')}"
            if pointer:
                candidates.append({"description": text, "source_ref": pointer})
    return candidates


def _department(buckets: dict[str, list[dict[str, Any]]]) -> str:
    labels = (
        ("Procurement", r"\bprocurement\b"),
        ("Accounts Payable", r"\baccounts payable\b"),
        ("Finance", r"\bfinance\b"),
        ("HR", r"\bhuman resources\b|\bhr\b"),
        ("Operations", r"\boperations\b"),
        ("AP", r"\bap\b"),
    )
    for entry in buckets.get("people_and_roles", []) + buckets.get("facts", []):
        text = entry["statement"]
        for label, pattern in labels:
            if re.search(pattern, text, re.I):
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
