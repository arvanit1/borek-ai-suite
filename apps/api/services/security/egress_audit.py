"""Path-only audit of outbound classification decisions. Never stores field values."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterator
from uuid import UUID

logger = logging.getLogger(__name__)

_SKIP_NESTED_RECORD: ContextVar[bool] = ContextVar("skip_nested_egress_record", default=False)


@dataclass(frozen=True)
class EgressFieldDecision:
    field: str
    classification: str
    decision: str

    def to_json_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "classification": self.classification,
            "decision": self.decision,
        }


@dataclass(frozen=True)
class EgressAuditRecord:
    provider: str
    stage: str
    allowed_paths: tuple[str, ...]
    blocked_paths: tuple[str, ...]
    journey_stage: str | None = None
    opportunity_id: str | None = None
    presentation_version_id: str | None = None
    fields: tuple[EgressFieldDecision, ...] = ()
    attempt: int = 1
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "stage": self.stage,
            "journey_stage": self.journey_stage,
            "opportunity_id": self.opportunity_id,
            "presentation_version_id": self.presentation_version_id,
            "allowed_paths": list(self.allowed_paths),
            "blocked_paths": list(self.blocked_paths),
            "fields": [item.to_json_dict() for item in self.fields],
            "attempt": self.attempt,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
        }


_RECORDS: list[EgressAuditRecord] = []


@contextmanager
def skip_nested_egress_records() -> Iterator[None]:
    """One logical provider send must produce one audit row."""
    token = _SKIP_NESTED_RECORD.set(True)
    try:
        yield
    finally:
        _SKIP_NESTED_RECORD.reset(token)


def field_decisions_for(
    *,
    allowed_paths: tuple[str, ...],
    blocked_paths: tuple[str, ...],
    classifications: dict[str, Any],
) -> tuple[EgressFieldDecision, ...]:
    from services.security.egress_filter import classification_for_path

    decisions: list[EgressFieldDecision] = []
    for path in allowed_paths:
        classified = classification_for_path(path, classifications)
        decisions.append(
            EgressFieldDecision(
                field=path,
                classification=classified.value if classified is not None else "unclassified",
                decision="allowed",
            )
        )
    for path in blocked_paths:
        classified = classification_for_path(path, classifications)
        decisions.append(
            EgressFieldDecision(
                field=path,
                classification=classified.value if classified is not None else "unclassified",
                decision="blocked",
            )
        )
    return tuple(decisions)


def record_egress_decision(
    *,
    provider: str,
    stage: str,
    allowed_paths: tuple[str, ...],
    blocked_paths: tuple[str, ...],
    journey_stage: str | None = None,
    opportunity_id: str | None = None,
    presentation_version_id: str | None = None,
    fields: tuple[EgressFieldDecision, ...] | None = None,
    attempt: int = 1,
    store: Any | None = None,
    actor_id: Any | None = None,
) -> EgressAuditRecord | None:
    if _SKIP_NESTED_RECORD.get():
        return None
    record = EgressAuditRecord(
        provider=provider,
        stage=stage,
        allowed_paths=allowed_paths,
        blocked_paths=blocked_paths,
        journey_stage=journey_stage,
        opportunity_id=str(opportunity_id) if opportunity_id is not None else None,
        presentation_version_id=(
            str(presentation_version_id) if presentation_version_id is not None else None
        ),
        fields=fields or (),
        attempt=attempt,
    )
    _RECORDS.append(record)
    _persist_durable_record(record, store=store, actor_id=actor_id)
    return record


def list_egress_decisions() -> list[EgressAuditRecord]:
    return list(_RECORDS)


def reset_egress_decisions() -> None:
    _RECORDS.clear()


def _as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _persist_durable_record(
    record: EgressAuditRecord,
    *,
    store: Any | None,
    actor_id: Any | None,
) -> None:
    if store is None or not record.opportunity_id or not record.presentation_version_id:
        return
    if not record.journey_stage:
        return
    appender = getattr(store, "append_egress_audit", None)
    if appender is None:
        return
    outcome = "blocked" if record.blocked_paths else "allowed"
    try:
        appender(
            opportunity_id=record.opportunity_id,
            presentation_version_id=record.presentation_version_id,
            journey_stage=record.journey_stage,
            provider=record.provider,
            pipeline_stage=record.stage,
            decision=outcome,
            fields=[item.to_json_dict() for item in record.fields],
            attempt=record.attempt,
        )
    except Exception:
        logger.warning(
            "Durable egress audit write failed for %s %s; continuing",
            record.provider,
            record.presentation_version_id,
            exc_info=True,
        )
        return
    parsed_actor = _as_uuid(actor_id)
    parsed_version = _as_uuid(record.presentation_version_id)
    if parsed_actor is None or parsed_version is None:
        return
    try:
        from app.services.audit.audit_log import AuditObjectType, record_audit_event

        record_audit_event(
            store,
            actor_id=parsed_actor,
            action=f"egress.{outcome}",
            object_type=AuditObjectType.PRESENTATION,
            object_id=parsed_version,
        )
    except Exception:
        logger.warning(
            "AT-52 egress audit write failed for %s; continuing",
            record.presentation_version_id,
            exc_info=True,
        )
