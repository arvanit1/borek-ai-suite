"""JJ-11..JJ-13: Group B business rules that JSON Schema cannot express."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

__all__ = [
    "GroupBBusinessRuleError",
    "validate_group_b_business_rules",
]


class GroupBBusinessRuleError(ValueError):
    """A Group B SlideSpec violates a semantic business rule."""


_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_ISO_MONTH = re.compile(r"\b(\d{4}-\d{2})\b")
_WEEK = re.compile(r"\bweek\s+(\d+)\b", re.IGNORECASE)
_LEADING_NEGATIVE = re.compile(r"(?<!\d)[-−](\d+(?:[.,]\d+)?)")
_DATE_RANGE_SPLIT = re.compile(r"\s+(?:to|through|until)\s+|[–—]", re.IGNORECASE)


def validate_group_b_business_rules(slide_spec: dict[str, Any]) -> None:
    """Fail before rendering when a Group B spec breaks JJ-11..JJ-13."""
    layout_id = slide_spec.get("layoutId")
    if layout_id == "TIMELINE_01":
        _validate_timeline_date_range(slide_spec)
        _validate_unique_milestone_ids(
            slide_spec.get("milestones"),
            layout_id="TIMELINE_01",
        )
    elif layout_id == "MILESTONES_01":
        _validate_unique_milestone_ids(
            slide_spec.get("milestones"),
            layout_id="MILESTONES_01",
        )
    elif layout_id == "TEAM_FTE_01":
        _validate_non_negative_fte(slide_spec)


def _validate_timeline_date_range(slide_spec: dict[str, Any]) -> None:
    dated_items: list[tuple[str, str]] = []
    for index, phase in enumerate(_as_list(slide_spec.get("phases"))):
        if isinstance(phase, dict):
            blob = " ".join(
                str(phase[key])
                for key in ("name", "description")
                if isinstance(phase.get(key), str)
            )
            dated_items.append((f"phases[{index}]", blob))
    for index, milestone in enumerate(_as_list(slide_spec.get("milestones"))):
        if isinstance(milestone, dict) and isinstance(milestone.get("date"), str):
            dated_items.append((f"milestones[{index}].date", milestone["date"]))

    for path, text in dated_items:
        start, end = _range_in_text(text)
        if start is not None and end is not None and end < start:
            raise GroupBBusinessRuleError(
                f"TIMELINE_01 date range at {path} has end before start"
            )

    ordered = []
    for path, text in dated_items:
        parsed = _parse_dates(text)
        if parsed:
            ordered.append((path, parsed[0]))

    for previous, current in zip(ordered, ordered[1:]):
        prev_kind, prev_value = previous[1]
        curr_kind, curr_value = current[1]
        if prev_kind == curr_kind and curr_value < prev_value:
            raise GroupBBusinessRuleError(
                "TIMELINE_01 timeline end must be on or after timeline start "
                f"({current[0]} precedes {previous[0]})"
            )


def _validate_non_negative_fte(slide_spec: dict[str, Any]) -> None:
    for index, role in enumerate(_as_list(slide_spec.get("roles"))):
        if not isinstance(role, dict) or not isinstance(role.get("fte"), str):
            continue
        if _contains_negative_number(role["fte"]):
            raise GroupBBusinessRuleError(
                f"TEAM_FTE_01 roles[{index}].fte must not be negative"
            )
    for index, stat in enumerate(_as_list(slide_spec.get("summary"))):
        if not isinstance(stat, dict):
            continue
        label = stat.get("label")
        value = stat.get("value")
        if isinstance(label, str) and "fte" in label.casefold() and isinstance(value, str):
            if _contains_negative_number(value):
                raise GroupBBusinessRuleError(
                    f"TEAM_FTE_01 summary[{index}].value must not be negative"
                )


def _validate_unique_milestone_ids(milestones: Any, *, layout_id: str) -> None:
    identities: list[str] = []
    for item in _as_list(milestones):
        if not isinstance(item, dict):
            continue
        identity = item.get("id")
        if not isinstance(identity, str) or not identity:
            identity = item.get("name")
        if isinstance(identity, str) and identity:
            identities.append(identity)
    if len(identities) != len(set(identities)):
        raise GroupBBusinessRuleError(
            f"{layout_id} milestones must not share an id"
        )


def _contains_negative_number(text: str) -> bool:
    return _LEADING_NEGATIVE.search(text) is not None


def _range_in_text(text: str) -> tuple[tuple[str, int] | None, tuple[str, int] | None]:
    parts = [part.strip() for part in _DATE_RANGE_SPLIT.split(text) if part.strip()]
    if len(parts) < 2:
        dates = _parse_dates(text)
        if len(dates) >= 2:
            return dates[0], dates[-1]
        return None, None
    start_dates = _parse_dates(parts[0])
    end_dates = _parse_dates(parts[-1])
    if start_dates and end_dates:
        return start_dates[0], end_dates[-1]
    return None, None


def _parse_dates(text: str) -> list[tuple[str, int]]:
    found: list[tuple[int, tuple[str, int]]] = []
    for match in _ISO_DATE.finditer(text):
        parsed = date.fromisoformat(match.group(1))
        found.append((match.start(), ("day", parsed.toordinal())))
    for match in _ISO_MONTH.finditer(text):
        if _ISO_DATE.match(text, match.start()):
            continue
        year_s, month_s = match.group(1).split("-")
        parsed = date(int(year_s), int(month_s), 1)
        found.append((match.start(), ("month", parsed.toordinal())))
    for match in _WEEK.finditer(text):
        found.append((match.start(), ("week", int(match.group(1)))))
    found.sort(key=lambda item: item[0])
    return [item[1] for item in found]


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
