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
_RICH_FIXTURE_PATH = (
    Path(__file__).resolve().parents[5]
    / "tests"
    / "fixtures"
    / "framework_object.confirmed.group_a.json"
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


def load_framework_stub_template(opportunity_id: UUID) -> dict[str, Any]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    if _RICH_FIXTURE_PATH.is_file():
        rich = json.loads(_RICH_FIXTURE_PATH.read_text(encoding="utf-8"))
        for index, chapter in enumerate(payload.get("chapters", [])):
            rich_chapter = rich.get("chapters", [])[index] if index < len(rich.get("chapters", [])) else None
            if rich_chapter and rich_chapter.get("source_refs"):
                chapter["body"] = copy.deepcopy(rich_chapter.get("body", chapter.get("body")))
                chapter["source_refs"] = copy.deepcopy(rich_chapter.get("source_refs", []))
        payload["quality_scores"] = copy.deepcopy(rich.get("quality_scores", payload["quality_scores"]))
        payload["kpis"] = copy.deepcopy(rich.get("kpis", payload["kpis"]))
        payload["rules"] = copy.deepcopy(rich.get("rules", payload["rules"]))
    _inject_es13_ai_split(payload)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload["opportunity_id"] = str(opportunity_id)
    payload["updated_at"] = now
    payload["created_at"] = now
    return payload
