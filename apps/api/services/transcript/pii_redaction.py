"""ES-4 — strip names, emails, and phones before any LLM call.

The original turns stay with the caller for storage. This module only returns
the redacted copy that is safe to send to a provider. Toggle per opportunity
with ``enabled``; when omitted, ``config/pii_redaction.yaml`` is used.

Person names are redacted; named systems, products, and process labels are
preserved so ES-5 extraction can retain them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from services.transcript.speaker_turns import UNKNOWN_SPEAKER, SpeakerTurn

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_PATH = _REPO_ROOT / "config" / "pii_redaction.yaml"

_EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_NAME_PAIR_RE = re.compile(
    r"(?<![\w-])"
    r"([\w\u00C0-\u024F][\w\u00C0-\u024F'-]{1,}|[A-Z]{2,})"
    r"\s+"
    r"([\w\u00C0-\u024F][\w\u00C0-\u024F'-]{1,}|[A-Z]{2,})"
    r"(?![\w-])",
    re.UNICODE,
)
_CONTEXTUAL_NAME_RE = re.compile(
    r"\b(?:ask|call|email|contact|escalate to|loop in|reach out to|notify|tell|cc)\s+"
    r"([\w\u00C0-\u024F][\w\u00C0-\u024F'-]{1,})"
    r"(?![\w-])",
    re.IGNORECASE | re.UNICODE,
)
_NAME_FALSE_POSITIVES = frozenset(
    {
        "purchase order",
        "goods receipt",
        "exception queue",
        "human control",
        "data classification",
        "data residency",
        "data minimization",
        "open item",
        "business case",
        "evolution stage",
        "management summary",
        "building block",
        "delivery note",
        "accounts payable",
        "microsoft graph",
        "shared mailbox",
        "european union",
        "new hire",
        "oracle fusion",
        "microsoft dynamics",
        "invoice processing",
        "expense report",
        "goods receipt",
    }
)
_VENDOR_PREFIXES = frozenset(
    {
        "oracle",
        "microsoft",
        "sap",
        "salesforce",
        "google",
        "amazon",
        "ibm",
        "workday",
        "servicenow",
        "dynamics",
        "sharepoint",
        "concur",
    }
)
_BUSINESS_NOUNS = frozenset(
    {
        "fusion",
        "dynamics",
        "graph",
        "cloud",
        "erp",
        "365",
        "processing",
        "workflow",
        "mailbox",
        "queue",
        "portal",
        "platform",
        "suite",
        "office",
        "teams",
        "now",
        "receipt",
        "payable",
        "invoice",
        "invoices",
    }
)
_BUSINESS_SINGLE = frozenset(
    {
        "servicenow",
        "workday",
        "sharepoint",
        "salesforce",
        "concur",
        "dynamics",
        "oracle",
        "sap",
    }
)
_SINGLE_NAME_FALSE = frozenset(
    {
        "erp",
        "api",
        "pdf",
        "sap",
        "teams",
        "graph",
        "finance",
        "business",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "please",
        "thanks",
        "hello",
        "invoice",
        "processing",
        "servicenow",
        "oracle",
        "microsoft",
        "fusion",
        "dynamics",
    }
)

_PHONE_RE = re.compile(
    r"""
    (?<!\w)
    (?:
        \+\d{1,3}[\s./-]*
        (?:\(?\d{2,4}\)?[\s./-]*)?
        \d{3,4}[\s./-]*\d{3,6}
        |
        \(?\d{2,4}\)?[\s./-]*\d{3,4}[\s./-]*\d{3,6}
    )
    (?!\w)
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class PiiRedactionConfig:
    default_enabled: bool
    redact_emails: bool
    redact_phones: bool
    redact_names: bool
    email_placeholder: str
    phone_placeholder: str
    name_placeholder: str
    speaker_prefix: str


def load_pii_redaction_config(path: Path | None = None) -> PiiRedactionConfig:
    return _load_config(path or _CONFIG_PATH)


def is_redaction_enabled(opportunity_enabled: bool | None = None) -> bool:
    if opportunity_enabled is not None:
        return opportunity_enabled
    return load_pii_redaction_config().default_enabled


def redact_turns_for_llm(
    turns: list[SpeakerTurn],
    *,
    enabled: bool | None = None,
    config: PiiRedactionConfig | None = None,
) -> list[SpeakerTurn]:
    """Return a copy of turns with PII removed. Input list is not mutated."""
    settings = config or load_pii_redaction_config()
    if not is_redaction_enabled(enabled):
        return list(turns)

    speaker_aliases = _speaker_aliases(turns, settings.speaker_prefix) if settings.redact_names else {}
    single_names = _single_name_tokens(speaker_aliases)

    redacted: list[SpeakerTurn] = []
    for turn in turns:
        text = turn.text
        if settings.redact_emails:
            text = _EMAIL_RE.sub(settings.email_placeholder, text)
        if settings.redact_phones:
            text = _PHONE_RE.sub(settings.phone_placeholder, text)
        if settings.redact_names:
            text = _replace_names(text, speaker_aliases)
            text = _replace_person_name_pairs(text, settings.name_placeholder, speaker_aliases)
            text = _replace_contextual_person_names(text, settings.name_placeholder, speaker_aliases)
            text = _replace_single_names(text, single_names, settings.name_placeholder)
        speaker = speaker_aliases.get(turn.speaker, turn.speaker)
        redacted.append(
            SpeakerTurn(turn_index=turn.turn_index, speaker=speaker, text=text)
        )
    return redacted


@lru_cache(maxsize=4)
def _load_config(path: Path) -> PiiRedactionConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    redact = raw.get("redact") or {}
    placeholders = raw.get("placeholders") or {}
    return PiiRedactionConfig(
        default_enabled=bool(raw.get("default_enabled", True)),
        redact_emails=bool(redact.get("emails", True)),
        redact_phones=bool(redact.get("phones", True)),
        redact_names=bool(redact.get("names", True)),
        email_placeholder=str(placeholders.get("email", "[EMAIL]")),
        phone_placeholder=str(placeholders.get("phone", "[PHONE]")),
        name_placeholder=str(placeholders.get("name", "[NAME]")),
        speaker_prefix=str(placeholders.get("speaker_prefix", "SPEAKER")),
    )


def _speaker_aliases(turns: list[SpeakerTurn], prefix: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    next_index = 1
    for turn in turns:
        speaker = turn.speaker.strip()
        if not speaker or speaker.lower() == UNKNOWN_SPEAKER:
            continue
        if speaker not in aliases:
            aliases[speaker] = f"{prefix}_{next_index}"
            next_index += 1
    return aliases


def _single_name_tokens(speaker_aliases: dict[str, str]) -> set[str]:
    tokens: set[str] = set()
    for original in speaker_aliases:
        for part in re.split(r"\s+", original.strip()):
            if _looks_like_person_name_part(part):
                tokens.add(part)
    return tokens


def _replace_names(text: str, aliases: dict[str, str]) -> str:
    redacted = text
    for original, alias in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"(?<![\w-]){re.escape(original)}(?![\w-])", re.IGNORECASE | re.UNICODE)
        redacted = pattern.sub(alias, redacted)
    return redacted


def _replace_person_name_pairs(text: str, placeholder: str, speaker_aliases: dict[str, str]) -> str:
    """Redact third-party person names (First Last) that are not speaker labels."""
    alias_values = {value.lower() for value in speaker_aliases.values()}
    redacted = text
    for match in sorted(_NAME_PAIR_RE.finditer(text), key=lambda item: item.start(), reverse=True):
        pair = match.group(0)
        part1, part2 = match.group(1), match.group(2)
        if not _looks_like_person_name_part(part1) or not _looks_like_person_name_part(part2):
            continue
        lower = pair.lower()
        if lower in _NAME_FALSE_POSITIVES or _is_business_entity_pair(part1, part2):
            continue
        if pair.lower() in alias_values or pair in speaker_aliases:
            continue
        start, end = match.span()
        redacted = f"{redacted[:start]}{placeholder}{redacted[end:]}"
    return redacted


def _replace_contextual_person_names(text: str, placeholder: str, speaker_aliases: dict[str, str]) -> str:
    """Redact single first names only after explicit person-reference verbs."""
    alias_values = {value.lower() for value in speaker_aliases.values()}
    redacted = text
    for match in sorted(_CONTEXTUAL_NAME_RE.finditer(text), key=lambda item: item.start(), reverse=True):
        token = match.group(1)
        if not _looks_like_person_name_part(token):
            continue
        lower = token.lower()
        if lower in _SINGLE_NAME_FALSE or lower in _BUSINESS_SINGLE:
            continue
        if token in speaker_aliases or lower in alias_values:
            continue
        start, end = match.span(1)
        redacted = f"{redacted[:start]}{placeholder}{redacted[end:]}"
    return redacted


def _replace_single_names(text: str, tokens: set[str], placeholder: str) -> str:
    redacted = text
    for token in sorted(tokens, key=len, reverse=True):
        if token.lower() in _SINGLE_NAME_FALSE:
            continue
        pattern = re.compile(rf"(?<![\w-]){re.escape(token)}(?![\w-])", re.IGNORECASE | re.UNICODE)
        redacted = pattern.sub(placeholder, redacted)
    return redacted


def _is_business_entity_pair(part1: str, part2: str) -> bool:
    left = part1.lower()
    right = part2.lower()
    if left in _VENDOR_PREFIXES:
        return True
    if right in _BUSINESS_NOUNS:
        return True
    if left in _BUSINESS_NOUNS and right in _BUSINESS_NOUNS:
        return True
    return False


def _looks_like_person_name_part(word: str) -> bool:
    cleaned = word.strip("'-")
    if len(cleaned) < 2:
        return False
    if cleaned.lower() in _BUSINESS_SINGLE:
        return False
    if cleaned.isupper() and cleaned.isalpha():
        return True
    return cleaned[0].isupper() and any(ch.isalpha() for ch in cleaned[1:])
