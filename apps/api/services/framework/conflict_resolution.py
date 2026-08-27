"""ES-10 — later or confirmed source wins; else keep both. Never silent drop."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from services.knowledge_model.source_refs import source_id
from services.transcript.conversation_ids import CONVERSATION_ID_RE

_BUCKETS = (
    "facts",
    "stated_requirements",
    "constraints",
    "named_systems",
    "named_rules",
    "named_exceptions",
    "people_and_roles",
    "timeline_mentions",
    "risks",
    "unknowns",
)
_DIGIT_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def conversation_sort_key(conversation_id: str) -> int:
    match = CONVERSATION_ID_RE.fullmatch(conversation_id or "")
    return int(match.group(1)) if match else 0


def merge_knowledge_models(models: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Merge KnowledgeModels for the customer report.

    Priority: confirmed source, then later conversation_id (C8 over C5).
    The losing value is always recorded as an open item. If neither rule
    applies, both statements stay in the bucket.
    """
    if not models:
        return {bucket: [] for bucket in _BUCKETS}, []

    ordered = sorted(
        models,
        key=lambda item: conversation_sort_key(str(item.get("conversation_id", "C0"))),
    )
    merged: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in _BUCKETS}
    open_items: list[dict[str, Any]] = []

    for bucket in _BUCKETS:
        by_key: dict[str, list[tuple[bool, int, dict[str, Any]]]] = defaultdict(list)
        for model in ordered:
            cid = str(model.get("conversation_id", "C0"))
            rank = conversation_sort_key(cid)
            for entry in model.get(bucket) or []:
                statement = str(entry.get("statement", "")).strip()
                if not statement:
                    continue
                key = _resolve_topic_key(by_key, statement)
                by_key[key].append((_is_confirmed(model, entry), rank, entry))

        for key, versions in by_key.items():
            unique = _unique_statements(versions)
            if len(unique) == 1:
                merged[bucket].append(unique[0][2])
                continue

            confirmed_flags = {flag for flag, _rank, _entry in unique}
            ranks = {rank for _flag, rank, _entry in unique}
            if len(confirmed_flags) > 1 or len(ranks) > 1:
                winner = sorted(unique, key=_precedence)[-1][2]
                merged[bucket].append(winner)
            else:
                for _flag, _rank, entry in unique:
                    merged[bucket].append(entry)

            if bucket != "unknowns":
                open_items.append(_open_item(key, unique))

    return merged, open_items


def flatten_entries(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for bucket, items in buckets.items():
        for entry in items:
            packed = dict(entry)
            packed["bucket"] = bucket
            entries.append(packed)
    return entries


def _is_confirmed(model: dict[str, Any], entry: dict[str, Any]) -> bool:
    if entry.get("confirmed") is True:
        return True
    return str(model.get("status") or "").strip().lower() == "confirmed"


def _precedence(item: tuple[bool, int, dict[str, Any]]) -> tuple[int, int]:
    confirmed, rank, _entry = item
    return (int(confirmed), rank)


def _unique_statements(
    versions: list[tuple[bool, int, dict[str, Any]]],
) -> list[tuple[bool, int, dict[str, Any]]]:
    seen: dict[str, tuple[bool, int, dict[str, Any]]] = {}
    for item in versions:
        statement = str(item[2].get("statement", "")).strip()
        previous = seen.get(statement)
        if previous is None or _precedence(item) >= _precedence(previous):
            seen[statement] = item
    return sorted(seen.values(), key=_precedence)


def _open_item(topic: str, versions: list[tuple[bool, int, dict[str, Any]]]) -> dict[str, Any]:
    values = [str(entry.get("statement", "")).strip() for _flag, _rank, entry in versions]
    source_ids: list[str] = []
    for _flag, _rank, entry in versions:
        for ref in entry.get("source_refs") or []:
            if isinstance(ref, dict):
                source_ids.append(source_id(ref))
    quoted = " vs ".join(f"'{value}'" for value in values)
    confirmed_flags = {flag for flag, _rank, _entry in versions}
    ranks = {rank for _flag, rank, _entry in versions}
    if len(confirmed_flags) > 1:
        note = " Confirmed source kept as the working statement."
    elif len(ranks) > 1:
        note = " Later source kept as the working statement."
    else:
        note = " Sources are the same rank, so both statements are kept."
    sources = f" Sources: {', '.join(source_ids)}." if source_ids else ""
    return {
        "description": (
            f"Conflicting statements on '{topic}': {quoted}.{note}{sources} Requires clarification."
        ),
        "item_type": "assumption",
        "owner": "Process Manager",
        "consequence_if_different": "Re-run the originating conversation; do not guess a blend.",
    }


def _topic_key(statement: str) -> str:
    # Values are intentionally removed: "Tolerance is EUR 1.00" and
    # "Tolerance is EUR 0.50" concern the same topic, while a clean-case time
    # and an exception time do not merely because both mention "invoice".
    def preserve_speaker_identifier(match: re.Match[str]) -> str:
        digits = match.group(1)
        return " speaker_role_" + "_".join(_DIGIT_WORDS[digit] for digit in digits) + " "

    protected = re.sub(r"\bspeaker[_\s-]*(\d+)\b", preserve_speaker_identifier, statement.lower())
    cleaned = re.sub(r"\d+(?:[.,]\d+)?", " ", protected)
    cleaned = re.sub(r"[^a-z]+", " ", cleaned).strip()
    words = [word for word in cleaned.split() if word not in {"the", "a", "an", "of", "and", "to", "in", "is"}]
    return " ".join(words[:8]) or cleaned


def _resolve_topic_key(by_key: dict[str, list], statement: str) -> str:
    candidate = _topic_key(statement)
    # Do not heuristically merge different facts. A false conflict produces an
    # incorrect customer open item; exact semantic topic keys remain sufficient
    # for value changes extracted with the same subject wording.
    if candidate in by_key:
        return candidate
    return candidate
