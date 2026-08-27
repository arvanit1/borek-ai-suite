"""Customer-text guardrails: tasks not people, no citation leftovers, no invented numbers."""

from __future__ import annotations

import re
from typing import Any

from services.framework.assembly import allowed_customer_numbers

_CITATION_RE = re.compile(r"\[C\d+\s*:?\s*t?\d*\]", re.I)
_TURN_POINTER_RE = re.compile(r"\bturn:\d+\b", re.I)
_SPEAKER_RE = re.compile(r"\bSPEAKER_\d+\b", re.I)
_CUSTOMER_SKIP_KEYS = frozenset(
    {"source_refs", "excerpt_pointer", "conversation_id", "generated_from", "source_entries", "transcript_id"}
)
_PERSON_EVAL = re.compile(
    r"\b(lazy|incompetent|unskilled|careless|resistant|slow worker|underperform(?:er|ing))\b",
    re.I,
)
_SUPERLATIVE = re.compile(
    r"\b(best-in-class|world-class|revolutionary|guaranteed|unique(?:ly)? unmatched)\b",
    re.I,
)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.,-])(\d+(?:[.,]\d+)?)(?![A-Za-z0-9.,-])")


class GuardrailError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def strip_citations(text: str) -> str:
    cleaned = _CITATION_RE.sub("", text)
    cleaned = _TURN_POINTER_RE.sub("", cleaned)
    cleaned = _SPEAKER_RE.sub("a business stakeholder", cleaned)
    cleaned = re.sub(r"\ban tool\b", "a tool", cleaned, flags=re.I)
    return re.sub(r" {2,}", " ", cleaned).strip()


def strip_citations_from_value(value: Any) -> Any:
    if isinstance(value, str):
        return strip_citations(value)
    if isinstance(value, list):
        return [strip_citations_from_value(item) for item in value]
    if isinstance(value, dict):
        return {key: strip_citations_from_value(item) for key, item in value.items()}
    return value


def lint_customer_texts(framework: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    blob = _flatten_customer_text(framework)
    if _PERSON_EVAL.search(blob):
        errors.append("Person-evaluative language is not allowed. Write about tasks, not people.")
    if _SUPERLATIVE.search(blob):
        errors.append("Unsourced superlatives are not allowed in the customer report.")
    if _CITATION_RE.search(blob):
        errors.append("Citation markers must be stripped from the customer view.")
    return errors


def lint_numbers(framework: dict[str, Any], customer_text: str) -> list[str]:
    allowed = allowed_customer_numbers(framework)
    for bucket in (
        framework.get("assessments"),
        framework.get("quality_scores"),
        framework.get("estimate"),
        framework.get("business_case"),
        framework.get("evolution_stages"),
        framework.get("open_items"),
        framework.get("kpis"),
        framework.get("systems"),
        framework.get("rules"),
        framework.get("exceptions"),
        framework.get("access_needs"),
    ):
        for token in re.findall(r"\d+(?:[.,]\d+)?", _flatten_customer_text(bucket or {})):
            allowed.add(_norm(token.replace(",", "")))
            try:
                raw = float(token.replace(",", ""))
            except ValueError:
                continue
            if 0 < raw <= 1:
                allowed.add(_norm(raw * 100))
    errors: list[str] = []
    for match in _NUMBER_RE.finditer(customer_text):
        token = match.group(1).replace(",", "")
        try:
            number = float(token)
        except ValueError:
            continue
        if number in {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 24, 36}:
            continue
        if _norm(number) in allowed or _norm(int(number) if number.is_integer() else number) in allowed:
            continue
        nearby = customer_text[max(0, match.start() - 24) : match.end() + 24]
        prefix = customer_text[max(0, match.start() - 6) : match.start()].lower()
        if prefix.endswith("turn:"):
            continue
        if any(
            word in nearby.lower()
            for word in ("chapter", "page", "week", "w1", "w2", "w3", "stage", "v2", "opp-", "fw-", "turn:", "speaker_")
        ):
            continue
        if re.search(
            r"\d+\s+(?:knowledge entries|participants|speaker turns|labeled turns|turns)\b",
            nearby,
            re.I,
        ):
            continue
        errors.append(
            f"Number {match.group(1)} appears in the customer view but is not in the model ({nearby!r})."
        )
    return errors


def enforce_guardrails(framework: dict[str, Any], customer_view: dict[str, Any]) -> None:
    surface = {
        "cover": customer_view.get("cover"),
        "chapters": customer_view.get("chapters"),
    }
    errors = lint_customer_texts(surface)
    errors.extend(lint_numbers(framework, _flatten_customer_text(surface)))
    if errors:
        raise GuardrailError(" ".join(errors[:8]))


def convert_unsourced_claims(framework: dict[str, Any]) -> None:
    """ES-28 — number/rule/claim without a source is converted to an open item, not accepted."""
    chapter_text = _flatten_customer_text({"chapters": framework.get("chapters")})
    errors = lint_numbers(framework, chapter_text)
    tokens: list[str] = []
    for error in errors:
        match = re.search(r"Number (\S+) appears", error)
        if match:
            tokens.append(match.group(1).rstrip(".,;"))
    if not tokens:
        return
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
        framework.setdefault("open_items", []).append(
            {
                "description": (
                    f"Number {token} was not named in the conversations. "
                    "Recorded as an open item rather than guessed."
                ),
                "item_type": "assumption",
                "owner": "Business",
                "consequence_if_different": "Missing information is never guessed. Confirm the figure before it is used.",
            }
        )
    ordered.sort(key=len, reverse=True)
    for chapter in framework.get("chapters") or []:
        if isinstance(chapter, dict):
            chapter["body"] = _replace_unsourced_tokens(chapter.get("body"), ordered)
    _refresh_open_items_table(framework)


def _replace_unsourced_tokens(value: Any, tokens: list[str]) -> Any:
    if isinstance(value, str):
        text = value
        for token in tokens:
            # Keep an unsourced interval readable as an explicit open item,
            # rather than leaving fragments such as “every an open item
            # minutes” in a customer report.
            text = re.sub(
                rf"\bevery\s+{re.escape(token)}\s+(?:minutes?|hours?|days?)\b",
                "at a frequency recorded as an open item",
                text,
                flags=re.I,
            )
            escaped = re.escape(token)
            text = re.sub(rf"(?<![A-Za-z0-9.,-]){escaped}(?![A-Za-z0-9.,-])", "an open item", text)
        return text
    if isinstance(value, list):
        return [_replace_unsourced_tokens(item, tokens) for item in value]
    if isinstance(value, dict):
        return {key: _replace_unsourced_tokens(item, tokens) for key, item in value.items()}
    return value


def _refresh_open_items_table(framework: dict[str, Any]) -> None:
    rows = [
        [
            item.get("description", ""),
            item.get("item_type", ""),
            item.get("owner", ""),
            item.get("consequence_if_different", ""),
        ]
        for item in framework.get("open_items") or []
    ] or [["None recorded", "—", "—", "—"]]
    for chapter in framework.get("chapters") or []:
        if str(chapter.get("chapter_id")) != "11":
            continue
        for block in chapter.get("body") or []:
            if isinstance(block, dict) and block.get("block") == "table" and "open" in str(block.get("caption", "")).lower():
                block["rows"] = rows
                return


def _flatten_customer_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, (int, float)):
        return str(payload)
    if isinstance(payload, list):
        return " ".join(_flatten_customer_text(item) for item in payload)
    if isinstance(payload, dict):
        return " ".join(
            _flatten_customer_text(item)
            for key, item in payload.items()
            if key not in _CUSTOMER_SKIP_KEYS
        )
    return str(payload)


def _norm(value: float | int | str) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return str(number)
