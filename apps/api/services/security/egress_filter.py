"""Fail-closed field policy for data sent to external AI providers.

PII redaction and confidential-data classification solve different problems.
This module enforces the latter: every outbound field must be classified, and
restricted data can never leave Borek. Client-confidential fields additionally
need an explicit provider-specific allow-list entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Classification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CLIENT_CONFIDENTIAL = "client_confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class EgressPolicy:
    """Approved providers and exceptional client-confidential field paths."""

    approved_providers: frozenset[str]
    client_confidential_allowlist: dict[str, frozenset[str]] = field(default_factory=dict)

    def permits(
        self,
        *,
        provider: str,
        path: str,
        classification: Classification,
    ) -> bool:
        provider_key = provider.strip().lower()
        if provider_key not in self.approved_providers:
            return False
        if classification == Classification.RESTRICTED:
            return False
        if classification in {Classification.PUBLIC, Classification.INTERNAL}:
            return True
        return path_is_allowlisted(
            path,
            self.client_confidential_allowlist.get(provider_key, frozenset()),
        )


@dataclass(frozen=True)
class EgressDecision:
    payload: Any
    allowed_paths: tuple[str, ...]
    blocked_paths: tuple[str, ...]


_BLOCKED = object()


def _coerce_classification(raw: Classification | str | None) -> Classification | None:
    if raw is None:
        return None
    return raw if isinstance(raw, Classification) else Classification(raw)


def classification_for_path(
    path: str,
    classifications: dict[str, Classification | str],
) -> Classification | None:
    """Return the longest matching path or parent prefix classification."""
    current = path
    while True:
        raw = classifications.get(current)
        if raw is not None:
            return _coerce_classification(raw)
        if not current:
            return None
        current = current.rsplit("/", 1)[0]


def path_is_allowlisted(path: str, allowed: frozenset[str]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in allowed)


def _classification_for_path(
    path: str,
    classifications: dict[str, Classification | str],
) -> Classification | None:
    return classification_for_path(path, classifications)


def filter_external_payload(
    payload: Any,
    *,
    provider: str,
    classifications: dict[str, Classification | str],
    policy: EgressPolicy,
) -> EgressDecision:
    """Return an outbound payload containing only explicitly permitted leaves.

    Paths use JSON Pointer notation (for example ``/client/name``). An
    unclassified leaf is blocked. Empty containers left after filtering are
    omitted, preventing structural hints about restricted content.
    """

    allowed: list[str] = []
    blocked: list[str] = []

    def keep_empty_container(path: str, empty: Any) -> Any:
        classification = _classification_for_path(path, classifications)
        if classification is not None and policy.permits(
            provider=provider,
            path=path,
            classification=classification,
        ):
            allowed.append(path)
            return empty
        return _BLOCKED

    def visit(value: Any, path: str) -> Any:
        if isinstance(value, dict):
            if not value:
                return keep_empty_container(path, {})
            kept: dict[str, Any] = {}
            for key, child in value.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                child_path = f"{path}/{escaped}"
                filtered = visit(child, child_path)
                if filtered is not _BLOCKED:
                    kept[str(key)] = filtered
            return kept if kept else _BLOCKED

        if isinstance(value, list):
            if not value:
                return keep_empty_container(path, [])
            kept_list: list[Any] = []
            for index, child in enumerate(value):
                filtered = visit(child, f"{path}/{index}")
                if filtered is not _BLOCKED:
                    kept_list.append(filtered)
            return kept_list if kept_list else _BLOCKED

        classification = _classification_for_path(path, classifications)
        if classification is not None and policy.permits(
            provider=provider,
            path=path,
            classification=classification,
        ):
            allowed.append(path)
            return value

        blocked.append(path)
        return _BLOCKED

    filtered_payload = visit(payload, "")
    return EgressDecision(
        payload={} if filtered_payload is _BLOCKED else filtered_payload,
        allowed_paths=tuple(allowed),
        blocked_paths=tuple(blocked),
    )
