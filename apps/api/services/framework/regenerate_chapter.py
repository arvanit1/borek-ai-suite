"""ES-12 — regenerate one chapter + its source_refs; other chapters stay equal."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Callable

from services.framework.chapter_validators import validate_all_chapters
from services.framework.chapter_validators.base import chapter_by_id
from services.framework.chapter_validators.ch06_how_built import scrub_framework_chapter_6
from services.framework.pre_confirm_check import prepare_framework_for_confirm
from services.framework.source_traceability import attach_block_source_refs
from services.framework.customer_view import build_customer_view
from services.framework.store import save_framework_version
from services.framework.guardrails import strip_citations_from_value
from services.knowledge_model.source_refs import EXCERPT_POINTER_RE
from services.transcript.conversation_ids import CONVERSATION_ID_RE


class ChapterRegenError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def regenerate_chapter(
    framework: dict[str, Any],
    chapter_id: str,
    new_chapter: dict[str, Any],
    *,
    reason: str,
    now: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Replace one chapter. The original object is not mutated."""
    if str(framework.get("status") or "") == "confirmed":
        raise ChapterRegenError(
            "A confirmed customer report cannot be regenerated. Work from a draft."
        )
    target_id = str(chapter_id)
    current = chapter_by_id(framework, target_id)
    replacement = copy.deepcopy(new_chapter)
    if str(replacement.get("chapter_id")) != target_id:
        raise ChapterRegenError(f"Replacement chapter_id must stay {target_id}.")
    if replacement.get("title") != current.get("title"):
        raise ChapterRegenError("Chapter titles are fixed by chapter_registry.json.")
    _require_source_refs(replacement, target_id)
    if not replacement.get("body"):
        raise ChapterRegenError(f"Chapter {target_id} must include a body.")

    updated = copy.deepcopy(framework)
    save_framework_version(copy.deepcopy(framework))
    had_customer_view = "customer_view" in updated
    lang = str((updated.get("customer_view") or {}).get("render_language") or "en")
    updated.pop("customer_view", None)

    chapters: list[dict[str, Any]] = []
    replaced = False
    for chapter in updated["chapters"]:
        if str(chapter.get("chapter_id")) == target_id:
            chapters.append(replacement)
            replaced = True
        else:
            chapters.append(chapter)
    if not replaced:
        raise ChapterRegenError(f"Chapter {target_id} is missing.")
    updated["chapters"] = chapters

    stamp = (now or (lambda: datetime.now(timezone.utc)))().replace(microsecond=0).isoformat().replace("+00:00", "Z")
    previous_version = int(framework.get("version") or 1)
    updated["version"] = previous_version + 1
    updated["previous_version_id"] = f"{framework.get('id') or framework.get('framework_id')}:v{previous_version}"
    updated["updated_at"] = stamp
    updated["change_log"] = list(framework.get("change_log") or []) + [
        f"Chapter {target_id} regenerated: {reason}"
    ]
    scrub_framework_chapter_6(updated)
    prepare_framework_for_confirm(updated)
    attach_block_source_refs(updated, framework.get("source_entries") or [])
    validate_all_chapters(updated)
    if had_customer_view:
        updated["customer_view"] = strip_citations_from_value(build_customer_view(updated, lang=lang))
    return updated


def _require_source_refs(chapter: dict[str, Any], chapter_id: str) -> None:
    refs = chapter.get("source_refs")
    if not isinstance(refs, list) or not refs:
        raise ChapterRegenError(f"Chapter {chapter_id} must keep source_refs (conversation_id + turn pointer).")
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            raise ChapterRegenError(f"Chapter {chapter_id} source_refs[{index}] is invalid.")
        cid = str(ref.get("conversation_id") or "").strip()
        pointer = str(ref.get("excerpt_pointer") or "").strip()
        speaker = str(ref.get("speaker_role") or "").strip()
        if not CONVERSATION_ID_RE.fullmatch(cid):
            raise ChapterRegenError(
                f"Chapter {chapter_id} source_refs[{index}] needs a conversation_id like C1."
            )
        if not EXCERPT_POINTER_RE.fullmatch(pointer):
            raise ChapterRegenError(
                f"Chapter {chapter_id} source_refs[{index}] needs excerpt_pointer like turn:0."
            )
        if not speaker:
            raise ChapterRegenError(f"Chapter {chapter_id} source_refs[{index}] needs speaker_role.")
