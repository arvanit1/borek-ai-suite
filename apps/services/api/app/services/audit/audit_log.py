"""Shared audit logging utility — actor + action + timestamp on state changes (AT-52)."""

from __future__ import annotations

import logging
from enum import StrEnum
from uuid import UUID

from app.services.data import DataStore

logger = logging.getLogger(__name__)


class AuditAction(StrEnum):
    OPPORTUNITY_CREATE = "opportunity.create"
    OPPORTUNITY_UPDATE = "opportunity.update"
    CLIENT_LOGO_UPLOAD = "client_logo.upload"
    CLIENT_LOGO_REPLACE = "client_logo.replace"
    CLIENT_LOGO_DELETE = "client_logo.delete"
    TRANSCRIPT_UPLOAD = "transcript.upload"
    TRANSCRIPT_REGENERATE = "transcript.regenerate"
    TRANSCRIPT_DELETE = "transcript.delete"
    FRAMEWORK_GENERATE = "framework.generate"
    FRAMEWORK_REGENERATE_CHAPTER = "framework.regenerate_chapter"
    FRAMEWORK_CONFIRM = "framework.confirm"
    FRAMEWORK_UPDATE = "framework.update"
    FRAMEWORK_RENDER = "framework.render"
    PRESENTATION_PLAN_GENERATE = "presentation_plan.generate"
    PRESENTATION_GENERATE = "presentation.generate"
    SLIDE_REGENERATE = "slide.regenerate"
    SLIDE_CHANGE_LAYOUT = "slide.change_layout"


class AuditObjectType(StrEnum):
    OPPORTUNITY = "opportunity"
    CLIENT_LOGO = "client_logo"
    TRANSCRIPT = "transcript"
    FRAMEWORK_VERSION = "framework_version"
    PRESENTATION_PLAN = "presentation_plan"
    PRESENTATION = "presentation"
    SLIDE = "slide"


def record_audit_event(
    store: DataStore,
    *,
    actor_id: UUID,
    action: AuditAction | str,
    object_type: AuditObjectType | str,
    object_id: UUID,
) -> None:
    """Persist actor, action, object reference, and timestamp for a state change.

    Audit writes must not fail the originating 202. A timeout on the audit
    insert after a successful enqueue is what produced "Failed to fetch" in
    the live UI.
    """
    try:
        store.append_audit_log(
            actor_id=actor_id,
            action=str(action),
            object_type=str(object_type),
            object_id=object_id,
        )
    except Exception:
        logger.warning(
            "Audit log write failed for %s on %s %s; continuing",
            action,
            object_type,
            object_id,
            exc_info=True,
        )
