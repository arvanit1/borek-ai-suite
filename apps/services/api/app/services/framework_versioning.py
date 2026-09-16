"""Stable revision fingerprints for optimistic Framework version creation."""

from __future__ import annotations

import hashlib
import copy
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from services.framework.customer_view import build_customer_view
from services.framework.guardrails import strip_citations_from_value


def framework_source_revision(row: dict[str, Any]) -> str:
    payload = {
        "status": row.get("status"),
        "framework_json": row.get("framework_json"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def framework_transition_id(source_id: uuid.UUID, transition: str) -> uuid.UUID:
    return uuid.uuid5(source_id, f"framework-{transition}:v1")


def build_framework_successor(
    source_row: dict[str, Any],
    *,
    status: str,
    change: str,
    framework_json: dict[str, Any] | None = None,
    confirmed_by: uuid.UUID | None = None,
    now: datetime | None = None,
    rebuild_customer_view: bool = True,
) -> dict[str, Any]:
    """Build a validated successor without mutating the source row or JSON."""
    source_json = source_row["framework_json"]
    source_version = int(source_row["version_number"])
    if int(source_json.get("version") or 0) != source_version:
        raise ValueError("Framework JSON version does not match its persisted version number")
    if str(source_json.get("status") or "") != str(source_row["status"]):
        raise ValueError("Framework JSON status does not match its persisted status")

    successor = copy.deepcopy(framework_json if framework_json is not None else source_json)
    stamp = (now or datetime.now(UTC)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    successor["opportunity_id"] = str(source_row["opportunity_id"])
    successor["version"] = source_version + 1
    successor["previous_version_id"] = str(source_row["id"])
    successor["status"] = status
    successor["created_at"] = stamp
    successor["updated_at"] = stamp
    successor["change_log"] = list(source_json.get("change_log") or []) + [change]
    successor.pop("confirmed_by", None)
    successor.pop("confirmed_at", None)
    if status == "confirmed":
        if confirmed_by is None:
            raise ValueError("A confirmed Framework successor requires confirmed_by")
        successor["confirmed_by"] = str(confirmed_by)
        successor["confirmed_at"] = stamp

    lang = str((source_json.get("customer_view") or {}).get("render_language") or "en")
    if rebuild_customer_view:
        successor.pop("customer_view", None)
        successor["customer_view"] = strip_citations_from_value(build_customer_view(successor, lang=lang))
    elif isinstance(source_json.get("customer_view"), dict):
        view = copy.deepcopy(source_json["customer_view"])
        for field in (
            "version",
            "previous_version_id",
            "status",
            "created_at",
            "updated_at",
            "change_log",
            "confirmed_by",
            "confirmed_at",
        ):
            if field in successor:
                view[field] = copy.deepcopy(successor[field])
            else:
                view.pop(field, None)
        successor["customer_view"] = view
    else:
        successor.pop("customer_view", None)
    return successor
