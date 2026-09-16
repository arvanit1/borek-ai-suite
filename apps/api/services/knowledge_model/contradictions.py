"""ES-8 — conflicting values become a structured object; never silently pick one."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from services.knowledge_model.source_refs import iter_knowledge_entries, source_id

_COMPARE_BUCKETS = frozenset(
    {
        "facts",
        "stated_requirements",
        "constraints",
        "named_rules",
        "named_systems",
    }
)


def detect_contradictions(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Return conflict objects. Does not drop or merge either value."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for bucket, _index, entry in iter_knowledge_entries(model):
        if bucket not in _COMPARE_BUCKETS:
            continue
        statement = str(entry.get("statement") or "").strip()
        if not statement:
            continue
        groups[(bucket, _topic_key(statement))].append(entry)

    conflicts: list[dict[str, Any]] = []
    for (bucket, topic), entries in groups.items():
        unique = _unique_by_statement(entries)
        if len(unique) < 2:
            continue
        values = [str(item["statement"]).strip() for item in unique]
        source_ids: list[str] = []
        alternatives: list[dict[str, Any]] = []
        for item in unique:
            refs = _sorted_refs(item.get("source_refs") or [])
            alternatives.append({"value": str(item["statement"]).strip(), "source_refs": refs})
            for ref in item.get("source_refs") or []:
                if isinstance(ref, dict):
                    source_ids.append(source_id(ref))
        conflicts.append(
            {
                "topic": topic,
                "bucket": bucket,
                "alternatives": alternatives,
                "values": values,
                "source_ids": source_ids,
                "requires_clarification": True,
            }
        )
    return conflicts


def _sorted_refs(refs: list[Any]) -> list[dict[str, str]]:
    unique = {
        (
            str(ref.get("conversation_id") or ""),
            str(ref.get("speaker_role") or ""),
            str(ref.get("excerpt_pointer") or ""),
        )
        for ref in refs
        if isinstance(ref, dict)
    }
    return [
        {"conversation_id": cid, "speaker_role": speaker, "excerpt_pointer": pointer}
        for cid, speaker, pointer in sorted(unique)
    ]


def _unique_by_statement(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for entry in entries:
        statement = str(entry.get("statement") or "").strip()
        if statement not in seen:
            seen[statement] = entry
    return [seen[key] for key in sorted(seen)]


def _topic_key(statement: str) -> str:
    cleaned = re.sub(r"[^a-z]+", " ", statement.lower()).strip()
    words = [word for word in cleaned.split() if word not in {"the", "a", "an", "of", "and", "to", "in", "is"}]
    return " ".join(words[:8]) or cleaned
