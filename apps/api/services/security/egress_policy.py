"""Load the machine-readable O4 policy and enforce it on every external send."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from services.security.egress_audit import record_egress_decision
from services.security.egress_filter import (
    Classification,
    EgressPolicy,
    classification_for_path,
    filter_external_payload,
)

_POLICY_PATH = Path(__file__).resolve().parents[4] / "config" / "data_egress_policy.yaml"


class EgressBlockedError(RuntimeError):
    """Live send rejected because a field was unclassified, restricted, or not allow-listed."""

    def __init__(self, provider: str, blocked_paths: tuple[str, ...]) -> None:
        super().__init__(
            "External payload contains blocked or unclassified fields: "
            + ", ".join(blocked_paths)
        )
        self.code = "EGRESS_BLOCKED"
        self.retryable = False
        self.provider = provider
        self.blocked_paths = blocked_paths


@lru_cache(maxsize=1)
def _raw_policy() -> dict[str, Any]:
    return yaml.safe_load(_POLICY_PATH.read_text(encoding="utf-8")) or {}


def reset_egress_policy_cache() -> None:
    _raw_policy.cache_clear()


def load_field_classifications() -> dict[str, str]:
    raw = _raw_policy().get("field_classifications") or {}
    return {str(path): str(value) for path, value in raw.items()}


def load_runtime_egress_policy() -> EgressPolicy:
    raw = _raw_policy()
    allowlist = {
        str(provider): frozenset(str(path) for path in paths or [])
        for provider, paths in (raw.get("client_confidential_allowlist") or {}).items()
    }
    return EgressPolicy(
        approved_providers=frozenset(
            str(item) for item in (raw.get("approved_providers") or [])
        ),
        client_confidential_allowlist=allowlist,
    )


def slot_classifications_from_policy(slot_names: list[str] | tuple[str, ...]) -> dict[str, str]:
    fields = load_field_classifications()
    classified: dict[str, str] = {}
    for name in slot_names:
        classification = classification_for_path(f"/slots/{name}", fields)
        if classification is not None:
            classified[name] = classification.value
    return classified


def enforce_external_egress(
    payload: Any,
    *,
    provider: str,
    stage: str,
    extra_classifications: dict[str, str] | None = None,
) -> Any:
    """Filter a structured payload and refuse the send if any leaf is blocked."""
    classifications: dict[str, Classification | str] = dict(load_field_classifications())
    if extra_classifications:
        classifications.update(extra_classifications)
    decision = filter_external_payload(
        payload,
        provider=provider,
        classifications=classifications,
        policy=load_runtime_egress_policy(),
    )
    record_egress_decision(
        provider=provider,
        stage=stage,
        allowed_paths=decision.allowed_paths,
        blocked_paths=decision.blocked_paths,
    )
    if decision.blocked_paths:
        raise EgressBlockedError(provider, decision.blocked_paths)
    return decision.payload
