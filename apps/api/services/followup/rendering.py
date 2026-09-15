"""BT-33 — deterministic follow-up email renderer (JSON → draft)."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema

from services.followup.errors import FollowupRenderError
from services.followup.extraction import load_followup_extraction_schema, validate_followup_extraction

_REPO_ROOT = Path(__file__).resolve().parents[4]
_STATICS_SCHEMA_PATH = _REPO_ROOT / "packages" / "contracts" / "followup_project_statics.schema.json"
_DRAFT_SCHEMA_PATH = _REPO_ROOT / "packages" / "contracts" / "followup_draft.schema.json"

_PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")
_DATE_RE = re.compile(r"^[0-9]{2}\.[0-9]{2}\.[0-9]{4}$")

ACTION_OVERFLOW_FLAG = "action_overflow_see_protocol"
KEY_POINTS_OVERFLOW_FLAG = "key_points_overflow_see_protocol"

MAX_BODY_WORDS = 150
MAX_KEY_POINTS = 3
MAX_ACTION_ITEMS = 5

_ATTACHMENT_LINE = "Attached you will find {attachment_name} with the full detail."
_PROTOCOL_REF_ATTACHMENT = "Further detail is in the attached protocol."
_PROTOCOL_REF_MEETING = "Further detail is in the meeting protocol."
_NO_ACTIONS_FALLBACK = (
    "No action items from our side for now — we will come back to you once {dependency} is clarified."
)
_OPEN_QUESTIONS_HEADING = "Open from our side:"
_DECISIONS_HEADING = "Decisions"
_KEY_POINTS_HEADING = "Key points"
_NEXT_STEPS_HEADING = "Next steps"
_INTRO = (
    "thank you for your time {time_reference}. Below is a short summary of what "
    "we agreed, so we all work from the same picture."
)
_CLOSING = (
    "If anything here does not match your understanding, just let me know and I "
    "will correct it."
)
_SIGNATURE_LINE = "{sender_role} · BOREK"


def load_followup_project_statics_schema() -> dict[str, Any]:
    return json.loads(_STATICS_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_followup_draft_schema() -> dict[str, Any]:
    return json.loads(_DRAFT_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_followup_project_statics(payload: dict[str, Any]) -> dict[str, Any]:
    schema = load_followup_project_statics_schema()
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        raise FollowupRenderError(
            f"Project statics failed validation at {exc.json_path}: {exc.message}",
            code="FOLLOWUP_STATICS_INVALID",
        ) from exc
    if payload.get("salutation_style") == "formal":
        for field in ("salutation", "last_name"):
            if not str(payload.get(field) or "").strip():
                raise FollowupRenderError(
                    f"Formal salutation_style requires {field}.",
                    code="FOLLOWUP_STATICS_INVALID",
                )
    return payload


def validate_followup_draft(payload: dict[str, Any]) -> dict[str, Any]:
    schema = load_followup_draft_schema()
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        raise FollowupRenderError(
            f"Draft output failed validation at {exc.json_path}: {exc.message}",
            code="FOLLOWUP_DRAFT_INVALID",
        ) from exc
    return payload


def render_followup_draft(
    extraction: dict[str, Any],
    statics: dict[str, Any],
    *,
    attachment_name: str | None = None,
    client_addressed: bool = False,
    reviewed: bool = False,
) -> dict[str, Any]:
    """Render a follow-up draft from frozen extraction JSON and project statics."""
    snapshot = copy.deepcopy(extraction)
    validated_extraction = validate_followup_extraction(copy.deepcopy(extraction))
    validated_statics = validate_followup_project_statics(statics)

    if client_addressed and not reviewed:
        raise FollowupRenderError(
            "Client-addressed draft is forbidden before MS-32 review.",
            code="FOLLOWUP_CLIENT_UNREVIEWED",
        )

    _validate_dates(validated_extraction)
    project_name = str(validated_statics["project_name"]).strip()
    meeting_topic = str(validated_extraction["meeting_topic"]).strip()
    meeting_date = str(validated_extraction["meeting_date"]).strip()

    subject = f"{project_name} — Follow-up {meeting_topic} ({meeting_date})"

    review_flags = list(validated_extraction.get("review_flags") or [])
    key_points = list(validated_extraction.get("key_points") or [])[:MAX_KEY_POINTS]
    action_items = _sorted_actions(list(validated_extraction.get("action_items") or [])[:MAX_ACTION_ITEMS])
    open_questions = list(validated_extraction.get("open_questions") or [])
    decisions = list(validated_extraction.get("decisions") or [])
    next_meeting = validated_extraction.get("next_meeting")

    include_key_overflow = KEY_POINTS_OVERFLOW_FLAG in review_flags
    include_action_overflow = ACTION_OVERFLOW_FLAG in review_flags

    greeting = _greeting(validated_statics)
    signature = _signature(validated_statics)

    body = _assemble_body(
        greeting=greeting,
        signature=signature,
        statics=validated_statics,
        key_points=key_points,
        action_items=action_items,
        open_questions=open_questions,
        decisions=decisions,
        next_meeting=next_meeting,
        meeting_date=meeting_date,
        attachment_name=attachment_name,
        include_key_overflow=include_key_overflow,
        include_action_overflow=include_action_overflow,
        include_open_questions=bool(open_questions),
        include_decisions=bool(decisions),
        include_next_meeting=next_meeting is not None,
        include_attachment=bool(attachment_name),
    )

    _assert_no_placeholders(subject, body)
    _assert_word_limit(body, greeting, signature)

    draft = {
        "subject": subject,
        "body": body,
        "review_flags": review_flags,
        "attachment_name": attachment_name,
        "status": "draft",
    }
    validate_followup_draft(draft)

    if extraction != snapshot:
        raise FollowupRenderError(
            "Renderer must not mutate extraction JSON.",
            code="FOLLOWUP_INPUT_MUTATED",
        )
    return draft


def _validate_dates(extraction: dict[str, Any]) -> None:
    meeting_date = str(extraction.get("meeting_date") or "")
    if not _DATE_RE.fullmatch(meeting_date):
        raise FollowupRenderError(
            f"Invalid meeting_date: {meeting_date!r}",
            code="FOLLOWUP_DATE_INVALID",
        )
    _parse_display_date(meeting_date)
    for item in extraction.get("action_items") or []:
        due = str(item.get("due") or "")
        if due != "TBD" and not _DATE_RE.fullmatch(due):
            raise FollowupRenderError(
                f"Invalid action due date: {due!r}",
                code="FOLLOWUP_DATE_INVALID",
            )
        if due != "TBD":
            _parse_display_date(due)
    next_meeting = extraction.get("next_meeting")
    if isinstance(next_meeting, dict):
        date = str(next_meeting.get("date") or "")
        if not _DATE_RE.fullmatch(date):
            raise FollowupRenderError(
                f"Invalid next_meeting.date: {date!r}",
                code="FOLLOWUP_DATE_INVALID",
            )
        _parse_display_date(date)


def _parse_display_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%d.%m.%Y")
    except ValueError as exc:
        raise FollowupRenderError(
            f"Malformed date: {value!r}",
            code="FOLLOWUP_DATE_INVALID",
        ) from exc


def _due_sort_key(due: str) -> tuple[int, int]:
    if due == "TBD":
        return (1, 99999999)
    parsed = _parse_display_date(due)
    return (0, parsed.year * 10000 + parsed.month * 100 + parsed.day)


def _sorted_actions(action_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(action_items, key=lambda item: _due_sort_key(str(item.get("due") or "TBD")))
    for item in ordered:
        for field in ("action", "owner", "due"):
            if not str(item.get(field) or "").strip():
                raise FollowupRenderError(
                    f"Invalid action_items entry: missing {field}.",
                    code="FOLLOWUP_ACTION_INVALID",
                )
    return ordered


def _format_due(due: str) -> str:
    if due == "TBD":
        return "date to be confirmed"
    return due


def _greeting(statics: dict[str, Any]) -> str:
    if statics.get("salutation_style") == "formal":
        salutation = str(statics["salutation"]).strip()
        last_name = str(statics["last_name"]).strip()
        return f"Dear {salutation} {last_name},"
    first_name = str(statics["recipient_first_name"]).strip()
    return f"Hi {first_name},"


def _signature(statics: dict[str, Any]) -> str:
    sender_name = str(statics["sender_name"]).strip()
    sender_role = str(statics["sender_role"]).strip()
    return f"Best regards\n{sender_name}\n{_SIGNATURE_LINE.format(sender_role=sender_role)}"


def _protocol_ref(attachment_name: str | None) -> str:
    if attachment_name:
        return _PROTOCOL_REF_ATTACHMENT
    return _PROTOCOL_REF_MEETING


def _assemble_body(
    *,
    greeting: str,
    signature: str,
    statics: dict[str, Any],
    key_points: list[str],
    action_items: list[dict[str, Any]],
    open_questions: list[str],
    decisions: list[str],
    next_meeting: dict[str, Any] | None,
    meeting_date: str,
    attachment_name: str | None,
    include_key_overflow: bool,
    include_action_overflow: bool,
    include_open_questions: bool,
    include_decisions: bool,
    include_next_meeting: bool,
    include_attachment: bool,
) -> str:
    omission_order = ["next_meeting", "decisions", "open_questions", "attachment"]

    while True:
        sections = _body_sections(
            statics=statics,
            key_points=key_points,
            action_items=action_items,
            open_questions=open_questions if include_open_questions else [],
            decisions=decisions if include_decisions else [],
            next_meeting=next_meeting if include_next_meeting else None,
            meeting_date=meeting_date,
            attachment_name=attachment_name if include_attachment else None,
            include_key_overflow=include_key_overflow,
            include_action_overflow=include_action_overflow,
        )
        body = _join_sections(sections, greeting, signature)
        if _body_word_count(body, greeting, signature) <= MAX_BODY_WORDS:
            return body
        if not omission_order:
            raise FollowupRenderError(
                f"Body exceeds {MAX_BODY_WORDS} words after deterministic omissions.",
                code="FOLLOWUP_BODY_WORD_LIMIT",
            )
        omitted = omission_order.pop(0)
        if omitted == "next_meeting":
            include_next_meeting = False
        elif omitted == "decisions":
            include_decisions = False
        elif omitted == "open_questions":
            include_open_questions = False
        elif omitted == "attachment":
            include_attachment = False


def _body_sections(
    *,
    statics: dict[str, Any],
    key_points: list[str],
    action_items: list[dict[str, Any]],
    open_questions: list[str],
    decisions: list[str],
    next_meeting: dict[str, Any] | None,
    meeting_date: str,
    attachment_name: str | None,
    include_key_overflow: bool,
    include_action_overflow: bool,
) -> list[str]:
    sections: list[str] = []
    sections.append(_INTRO.format(time_reference=str(statics["time_reference"]).strip()))

    if key_points:
        lines = [_KEY_POINTS_HEADING, *[f"- {point.strip()}" for point in key_points]]
        if include_key_overflow:
            lines.append(_protocol_ref(attachment_name))
        sections.append("\n".join(lines))

    if action_items:
        action_lines = [
            _NEXT_STEPS_HEADING,
            *[
                f"- {str(item['action']).strip()} — {str(item['owner']).strip()}, by {_format_due(str(item['due']).strip())}"
                for item in action_items
            ],
        ]
        if include_action_overflow:
            action_lines.append(_protocol_ref(attachment_name))
        sections.append("\n".join(action_lines))
    else:
        dependency = str(statics.get("no_actions_dependency") or "the open points").strip()
        sections.append(_NO_ACTIONS_FALLBACK.format(dependency=dependency))

    if open_questions:
        lines = [_OPEN_QUESTIONS_HEADING, *[f"- {question.strip()}" for question in open_questions]]
        sections.append("\n".join(lines))

    if decisions:
        lines = [
            _DECISIONS_HEADING,
            *[f"- {decision.strip()} (agreed {meeting_date})" for decision in decisions],
        ]
        sections.append("\n".join(lines))

    if attachment_name:
        sections.append(_ATTACHMENT_LINE.format(attachment_name=attachment_name.strip()))

    if next_meeting is not None:
        date = str(next_meeting["date"]).strip()
        time_value = str(next_meeting["time"]).strip()
        sections.append(f"Next session: {date}, {time_value}.")

    sections.append(_CLOSING)
    return sections


def _join_sections(sections: list[str], greeting: str, signature: str) -> str:
    return "\n\n".join([greeting, *sections, signature])


def _body_word_count(body: str, greeting: str, signature: str) -> int:
    core = body
    if core.startswith(greeting):
        core = core[len(greeting) :].lstrip("\n")
    if core.endswith(signature):
        core = core[: -len(signature)].rstrip("\n")
    words = [word for word in re.split(r"\s+", core.strip()) if word]
    return len(words)


def _assert_no_placeholders(subject: str, body: str) -> None:
    combined = f"{subject}\n{body}"
    if _PLACEHOLDER_RE.search(combined):
        raise FollowupRenderError(
            "Rendered output contains leftover template placeholders.",
            code="FOLLOWUP_PLACEHOLDER_LEFTOVER",
        )


def _assert_word_limit(body: str, greeting: str, signature: str) -> None:
    count = _body_word_count(body, greeting, signature)
    if count > MAX_BODY_WORDS:
        raise FollowupRenderError(
            f"Rendered body is {count} words; maximum is {MAX_BODY_WORDS} excluding greeting and signature.",
            code="FOLLOWUP_BODY_WORD_LIMIT",
        )
