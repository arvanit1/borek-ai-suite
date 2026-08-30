"""Shared framework stub template for memory and Supabase stores."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[5]
    / "packages"
    / "contracts"
    / "fixtures"
    / "framework_object.minimal.json"
)
_RICH_FIXTURE_PATHS = tuple(
    Path(__file__).resolve().parents[5]
    / "tests"
    / "fixtures"
    / f"framework_object.confirmed.group_{group}.json"
    for group in ("a", "b", "c")
)

_STUB_AI_SPLIT: dict[str, Any] = {
    "block": "ai_split",
    "used_for": ["Reading documents into structured fields with confidence per field"],
    "not_used_for": [
        "Deciding whether a case matches",
        "Evaluating tolerances or thresholds",
        "Assessing any employee",
    ],
}


def _inject_es13_ai_split(payload: dict[str, Any]) -> None:
    for chapter in payload.get("chapters") or []:
        if str(chapter.get("chapter_id")) != "6":
            continue
        body = chapter.get("body")
        if not isinstance(body, list):
            body = []
            chapter["body"] = body
        if any(isinstance(block, dict) and block.get("block") == "ai_split" for block in body):
            return
        body.append(copy.deepcopy(_STUB_AI_SPLIT))
        return


def _merge_rich_chapters(payload: dict[str, Any], rich: dict[str, Any]) -> None:
    chapters_by_id = {
        str(chapter.get("chapter_id")): chapter
        for chapter in payload.get("chapters", [])
        if isinstance(chapter, dict)
    }
    for rich_chapter in rich.get("chapters", []):
        if not isinstance(rich_chapter, dict) or not rich_chapter.get("source_refs"):
            continue
        chapter = chapters_by_id.get(str(rich_chapter.get("chapter_id")))
        if chapter is None:
            continue

        existing_body = chapter.get("body")
        rich_body = copy.deepcopy(rich_chapter.get("body"))
        if isinstance(existing_body, list) and isinstance(rich_body, list):
            for block in rich_body:
                if block not in existing_body:
                    existing_body.append(block)
        elif not existing_body and rich_body:
            chapter["body"] = rich_body

        source_refs = chapter.setdefault("source_refs", [])
        for source_ref in copy.deepcopy(rich_chapter["source_refs"]):
            if source_ref not in source_refs:
                source_refs.append(source_ref)


def load_framework_stub_template(opportunity_id: UUID) -> dict[str, Any]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    for index, rich_fixture_path in enumerate(_RICH_FIXTURE_PATHS):
        if not rich_fixture_path.is_file():
            continue
        rich = json.loads(rich_fixture_path.read_text(encoding="utf-8"))
        _merge_rich_chapters(payload, rich)
        if index == 0:
            payload["quality_scores"] = copy.deepcopy(
                rich.get("quality_scores", payload["quality_scores"])
            )
            payload["kpis"] = copy.deepcopy(rich.get("kpis", payload["kpis"]))
            payload["rules"] = copy.deepcopy(rich.get("rules", payload["rules"]))
    _inject_es13_ai_split(payload)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload["opportunity_id"] = str(opportunity_id)
    payload["updated_at"] = now
    payload["created_at"] = now
    return payload
