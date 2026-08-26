"""MS-14: reject currency and ROI-style pricing on SUCCESS_METRICS_01.

Prompt text is not enough. This scan runs on the SlideSpec before it is accepted
and does not mutate the payload.
"""

from __future__ import annotations

import re
from typing import Any

SUCCESS_METRICS_LAYOUT_ID = "SUCCESS_METRICS_01"

# Identity / provenance keys are not slide copy.
_SKIP_KEYS = frozenset(
    {"schema_version", "slideId", "layoutId", "sourceChapterIds", "darkBackground"}
)

_CURRENCY_TEXT = re.compile(
    r"(?:[€£$]|\b(?:EUR|USD|GBP|CHF|PLN)\b|\b(?:euros?|dollars?|pounds?)\b)",
    re.IGNORECASE,
)
_ROI_STYLE = re.compile(
    r"\b(?:roi|return\s+on\s+investment|payback|pricing?|investment|revenue|budget)\b",
    re.IGNORECASE,
)
_COST_OR_SAVINGS = re.compile(r"\b(?:costs?|savings?)\b", re.IGNORECASE)
_NUMBER_TOKEN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?(?![\w])")


class ProhibitedCurrencyContentError(ValueError):
    """SUCCESS_METRICS_01 contains currency or ROI-style pricing copy."""


def reject_success_metrics_currency(slide_spec: dict[str, Any]) -> None:
    """Reject SUCCESS_METRICS_01 if any content string carries money or ROI language.

    Other layout ids are ignored. The payload is never stripped or rewritten.
    """
    if slide_spec.get("layoutId") != SUCCESS_METRICS_LAYOUT_ID:
        return

    hits = _find_prohibited_paths(slide_spec)
    if hits:
        raise ProhibitedCurrencyContentError(
            f"{SUCCESS_METRICS_LAYOUT_ID} contains prohibited currency or pricing "
            f"content at {hits[0]}"
        )


def _find_prohibited_paths(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, str):
        if _is_prohibited(value):
            hits.append(path)
        return hits
    if isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_find_prohibited_paths(item, f"{path}[{index}]"))
        return hits
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _SKIP_KEYS:
                continue
            hits.extend(_find_prohibited_paths(item, f"{path}.{key}"))
    return hits


def _is_prohibited(text: str) -> bool:
    if _CURRENCY_TEXT.search(text) or _ROI_STYLE.search(text):
        return True
    # "reduce processing costs" is allowed; "save 20% costs" is not.
    return bool(_COST_OR_SAVINGS.search(text) and _NUMBER_TOKEN.search(text))
