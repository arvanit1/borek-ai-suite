"""BT-3: load canonical chapter-to-layout planner guidance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CHAPTER_LAYOUT_MAP_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "contracts"
    / "chapter_layout_map.json"
)


class ChapterLayoutGuidanceError(ValueError):
    """The canonical chapter-to-layout guidance cannot be used safely."""


def load_chapter_layout_guidance() -> dict[str, Any]:
    """Load and structurally validate the canonical planner-guidance document."""
    try:
        raw = CHAPTER_LAYOUT_MAP_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ChapterLayoutGuidanceError(
            f"Unable to load chapter-layout guidance from "
            f"{CHAPTER_LAYOUT_MAP_PATH}: {exc}"
        ) from exc

    try:
        guidance = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ChapterLayoutGuidanceError(
            f"Malformed chapter-layout guidance at {CHAPTER_LAYOUT_MAP_PATH}: {exc}"
        ) from exc

    _validate_guidance(guidance)
    return guidance


def _validate_guidance(guidance: Any) -> None:
    if not isinstance(guidance, dict):
        raise ChapterLayoutGuidanceError(
            "chapter_layout_map.json must contain an object"
        )
    schema_version = guidance.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ChapterLayoutGuidanceError(
            "chapter_layout_map.json must contain schema_version"
        )
    description = guidance.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ChapterLayoutGuidanceError(
            "chapter_layout_map.json must contain a description"
        )

    mappings = guidance.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise ChapterLayoutGuidanceError(
            "chapter_layout_map.json must contain a non-empty mappings array"
        )

    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise ChapterLayoutGuidanceError(
                f"chapter_layout_map.json mappings[{index}] must be an object"
            )
        _validate_string_list(mapping, "chapters", index)
        _validate_string_list(mapping, "layoutIds", index)
        if "excludeMonetaryFields" in mapping and not isinstance(
            mapping["excludeMonetaryFields"], bool
        ):
            raise ChapterLayoutGuidanceError(
                "chapter_layout_map.json "
                f"mappings[{index}].excludeMonetaryFields must be a boolean"
            )


def _validate_string_list(mapping: dict[str, Any], key: str, index: int) -> None:
    values = mapping.get(key)
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(value, str) and value for value in values)
        or len(values) != len(set(values))
    ):
        raise ChapterLayoutGuidanceError(
            f"chapter_layout_map.json mappings[{index}].{key} must be a "
            "non-empty array of unique strings"
        )
