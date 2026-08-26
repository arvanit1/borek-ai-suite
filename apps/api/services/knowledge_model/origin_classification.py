"""ES-7 — origin + confidence on every knowledge entry."""

from __future__ import annotations

from typing import Any

from services.knowledge_model.source_refs import iter_knowledge_entries

ORIGIN_VALUES = frozenset({"SOURCE_FACT", "USER_INPUT", "AI_INFERENCE", "OPEN_QUESTION"})
CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})


class OriginClassificationError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def validate_origins(model: dict[str, Any]) -> None:
    """Fail if any entry is missing a valid origin or confidence."""
    issues: list[str] = []
    for bucket, index, entry in iter_knowledge_entries(model):
        loc = f"{bucket}[{index}]"
        origin = str(entry.get("origin") or "").strip()
        confidence = str(entry.get("confidence") or "").strip()
        if origin not in ORIGIN_VALUES:
            issues.append(
                f"{loc} origin must be one of {', '.join(sorted(ORIGIN_VALUES))}."
            )
        if confidence not in CONFIDENCE_VALUES:
            issues.append(
                f"{loc} confidence must be one of {', '.join(sorted(CONFIDENCE_VALUES))}."
            )
    if issues:
        raise OriginClassificationError(" ".join(issues))
