from __future__ import annotations

import re
from typing import Any

from services.framework.chapter_validators.base import ChapterIssue, blocks_of


_FORBIDDEN = (
    "pseudocode",
    "json schema",
    "json-schema",
    "openapi",
    "swagger",
    "payload example",
)
_REWRITE = (
    (re.compile(r"json[\s-]*schema", re.I), "named data fields"),
    (re.compile(r"\bopenapi\b", re.I), "system interface"),
    (re.compile(r"\bswagger\b", re.I), "system interface"),
    (re.compile(r"\bpseudocode\b", re.I), "build steps"),
    (re.compile(r"payload examples?", re.I), "examples of the data"),
)
_CODE_FENCE = re.compile(r"```[\s\S]*?```")


def scrub_technical_depth(value: Any) -> Any:
    """Customer chapter 6: CIO depth only — rewrite contract/code wording."""
    if isinstance(value, str):
        text = _CODE_FENCE.sub("", value)
        for pattern, replacement in _REWRITE:
            text = pattern.sub(replacement, text)
        return text
    if isinstance(value, list):
        return [scrub_technical_depth(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub_technical_depth(item) for key, item in value.items()}
    return value


def scrub_framework_chapter_6(framework: dict[str, Any]) -> dict[str, Any]:
    for chapter in framework.get("chapters") or []:
        if str(chapter.get("chapter_id")) == "6":
            chapter["body"] = scrub_technical_depth(chapter.get("body"))
    return framework


def validate(framework: dict[str, Any], chapter: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    tables = blocks_of(chapter, "table")
    table_blob = str(tables).lower()
    if not (framework.get("systems") or "system" in table_blob):
        issues.append(ChapterIssue("6", "systems", "Chapter 6 must include the systems landscape."))
    if "building block" not in table_blob and "building-block" not in table_blob:
        issues.append(ChapterIssue("6", "building_blocks", "Chapter 6 must include the building-blocks table."))
    if "protect" not in table_blob:
        issues.append(
            ChapterIssue("6", "building_protection", "Chapter 6 building blocks must include how each block is protected.")
        )
    splits = blocks_of(chapter, "ai_split")
    used = [item for block in splits for item in (block.get("used_for") or []) if str(item).strip()]
    not_used = [item for block in splits for item in (block.get("not_used_for") or []) if str(item).strip()]
    if not used or not not_used:
        issues.append(
            ChapterIssue("6", "ai_split", "Chapter 6 must always include AI used and AI not-used columns.")
        )
    blob = str(chapter.get("body")).lower()
    if any(token in blob for token in _FORBIDDEN):
        issues.append(
            ChapterIssue("6", "technical_depth", "Customer chapter 6 must not include contracts or pseudocode.")
        )
    return issues
