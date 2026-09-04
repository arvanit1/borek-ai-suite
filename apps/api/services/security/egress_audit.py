"""Path-only audit of outbound classification decisions. Never stores field values."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class EgressAuditRecord:
    provider: str
    stage: str
    allowed_paths: tuple[str, ...]
    blocked_paths: tuple[str, ...]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "stage": self.stage,
            "allowed_paths": list(self.allowed_paths),
            "blocked_paths": list(self.blocked_paths),
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
        }


_RECORDS: list[EgressAuditRecord] = []


def record_egress_decision(
    *,
    provider: str,
    stage: str,
    allowed_paths: tuple[str, ...],
    blocked_paths: tuple[str, ...],
) -> EgressAuditRecord:
    record = EgressAuditRecord(
        provider=provider,
        stage=stage,
        allowed_paths=allowed_paths,
        blocked_paths=blocked_paths,
    )
    _RECORDS.append(record)
    return record


def list_egress_decisions() -> list[EgressAuditRecord]:
    return list(_RECORDS)


def reset_egress_decisions() -> None:
    _RECORDS.clear()
