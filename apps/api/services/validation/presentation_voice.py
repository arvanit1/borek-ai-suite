"""Deterministic Borek CI voice checks for customer-facing SlideSpec prose."""

from __future__ import annotations

import re
from typing import Any

from services.presentation.ci_contract import banned_marketing_terms

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E0-\U0001F1FF"
    "]",
    flags=re.UNICODE,
)

_SKIP_KEYS = frozenset(
    {
        "schema_version",
        "layoutId",
        "slideId",
        "sourceChapterIds",
        "fieldProvenance",
        "source_refs",
        "excerpt_pointer",
        "conversation_id",
        "generated_from",
        "source_entries",
        "transcript_id",
        "chapter_id",
        "block",
        "kind",
        "status",
        "id",
        "number",
        "order",
    }
)

_BANNED_TERM_RES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(term)}\b", re.I), term) for term in banned_marketing_terms()
)


class PresentationVoiceError(ValueError):
    """Customer-facing SlideSpec copy violates Borek CI voice rules."""


def lint_slide_spec_voice(slide_spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, text in _iter_customer_prose(slide_spec):
        errors.extend(_lint_prose(text, path))
    return errors


def enforce_slide_spec_voice(slide_spec: dict[str, Any]) -> None:
    errors = lint_slide_spec_voice(slide_spec)
    if errors:
        raise PresentationVoiceError(errors[0])


def _lint_prose(text: str, path: str) -> list[str]:
    errors: list[str] = []
    stripped = text.strip()
    if not stripped:
        return errors
    if "!" in stripped:
        errors.append(f"{path}: exclamation marks are not allowed in customer-facing slide copy.")
    if _EMOJI_RE.search(stripped):
        errors.append(f"{path}: emoji are not allowed in customer-facing slide copy.")
    lowered = stripped.lower()
    for pattern, term in _BANNED_TERM_RES:
        if pattern.search(lowered):
            errors.append(
                f"{path}: banned marketing term {term!r} is not allowed in customer-facing slide copy."
            )
            break
    return errors


def _iter_customer_prose(value: Any, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, str):
        if _looks_like_url_or_identifier(value):
            return []
        return [(path, value)]
    if isinstance(value, list):
        collected: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            collected.extend(_iter_customer_prose(item, f"{path}[{index}]"))
        return collected
    if isinstance(value, dict):
        collected = []
        for key, item in value.items():
            if key in _SKIP_KEYS:
                continue
            if _looks_like_metadata_key(str(key)):
                continue
            collected.extend(_iter_customer_prose(item, f"{path}.{key}"))
        return collected
    return []


def _looks_like_metadata_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    return normalized.endswith("_id") or normalized.endswith("_ids") or normalized in {
        "mime_type",
        "width_px",
        "height_px",
    }


def _looks_like_url_or_identifier(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith(("http://", "https://", "artifact:", "urn:")):
        return True
    if re.fullmatch(r"[A-Za-z0-9._-]+", stripped) and len(stripped) <= 64:
        return True
    return False
