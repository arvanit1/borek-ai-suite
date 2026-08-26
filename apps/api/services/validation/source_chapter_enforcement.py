"""Shared field-level SlideSpec provenance enforcement for BT-14 / JJ-9 / MS-11."""

from __future__ import annotations

from typing import Any, Iterable

from services.validation.compression_retry import get_value_at_path

FIELD_PROVENANCE_KEY = "fieldProvenance"
SOURCE_CHAPTER_IDS_KEY = "sourceChapterIds"

_EXEMPT_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "layoutId",
        "slideId",
        SOURCE_CHAPTER_IDS_KEY,
        FIELD_PROVENANCE_KEY,
    }
)


class SourceChapterEnforcementError(ValueError):
    """A SlideSpec does not provide complete, valid field-level provenance."""


def populated_content_leaf_paths(slide_spec: dict[str, Any]) -> tuple[str, ...]:
    """Return canonical AT-8-style paths for populated, non-metadata content leaves."""
    if not isinstance(slide_spec, dict):
        raise SourceChapterEnforcementError("SlideSpec must be an object")

    paths: list[str] = []
    for key, value in slide_spec.items():
        if key in _EXEMPT_ROOT_FIELDS:
            continue
        _collect_populated_leaf_paths(value, key, paths)
    return tuple(paths)


def validate_field_provenance(
    slide_spec: dict[str, Any],
    *,
    real_chapter_ids: Iterable[str],
    allowed_chapter_ids: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    """Validate complete field provenance and return a canonical path-to-chapters map.

    The shared base schema keeps ``fieldProvenance`` optional for compatibility. Layout
    groups call this validator when their ticket begins enforcing the shared contract.
    """
    expected_paths = populated_content_leaf_paths(slide_spec)
    expected_path_set = set(expected_paths)
    provenance = slide_spec.get(FIELD_PROVENANCE_KEY)
    if not isinstance(provenance, list) or not provenance:
        raise SourceChapterEnforcementError(
            "fieldProvenance must be a non-empty array for generated SlideSpecs"
        )

    root_source_ids = slide_spec.get(SOURCE_CHAPTER_IDS_KEY)
    if (
        not isinstance(root_source_ids, list)
        or not root_source_ids
        or not all(isinstance(chapter_id, str) for chapter_id in root_source_ids)
        or len(set(root_source_ids)) != len(root_source_ids)
    ):
        raise SourceChapterEnforcementError(
            "sourceChapterIds must be a non-empty, duplicate-free string array"
        )

    root_source_set = set(root_source_ids)
    real_chapter_set = set(real_chapter_ids)
    allowed_chapter_set = set(allowed_chapter_ids)
    by_path: dict[str, tuple[str, ...]] = {}

    for index, entry in enumerate(provenance):
        if not isinstance(entry, dict) or set(entry) != {"path", SOURCE_CHAPTER_IDS_KEY}:
            raise SourceChapterEnforcementError(
                f"fieldProvenance[{index}] must contain only path and sourceChapterIds"
            )

        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise SourceChapterEnforcementError(
                f"fieldProvenance[{index}].path must be a non-empty string"
            )
        if path in by_path:
            raise SourceChapterEnforcementError(
                f"Duplicate fieldProvenance path: {path}"
            )

        try:
            value = get_value_at_path(slide_spec, path)
        except (IndexError, KeyError, TypeError) as exc:
            raise SourceChapterEnforcementError(
                f"fieldProvenance path does not resolve: {path}"
            ) from exc
        if path not in expected_path_set or not _is_populated_leaf(value):
            raise SourceChapterEnforcementError(
                f"fieldProvenance path is not a populated content leaf: {path}"
            )

        chapter_ids = entry.get(SOURCE_CHAPTER_IDS_KEY)
        if (
            not isinstance(chapter_ids, list)
            or not chapter_ids
            or not all(isinstance(chapter_id, str) for chapter_id in chapter_ids)
        ):
            raise SourceChapterEnforcementError(
                f"fieldProvenance sourceChapterIds must be non-empty at {path}"
            )
        if len(set(chapter_ids)) != len(chapter_ids):
            raise SourceChapterEnforcementError(
                f"fieldProvenance sourceChapterIds must be unique at {path}"
            )

        chapter_set = set(chapter_ids)
        unknown = chapter_set - real_chapter_set
        if unknown:
            raise SourceChapterEnforcementError(
                f"fieldProvenance references a non-existent Framework chapter at {path}: "
                f"{sorted(unknown)[0]}"
            )
        outside_allowed = chapter_set - allowed_chapter_set
        if outside_allowed:
            raise SourceChapterEnforcementError(
                f"fieldProvenance references a chapter outside the layout allowance at "
                f"{path}: {sorted(outside_allowed)[0]}"
            )
        outside_root = chapter_set - root_source_set
        if outside_root:
            raise SourceChapterEnforcementError(
                f"fieldProvenance chapter is absent from root sourceChapterIds at "
                f"{path}: {sorted(outside_root)[0]}"
            )

        by_path[path] = tuple(chapter_ids)

    missing_paths = expected_path_set - set(by_path)
    if missing_paths:
        raise SourceChapterEnforcementError(
            f"Missing fieldProvenance for populated content field: {sorted(missing_paths)[0]}"
        )

    provenance_union = {
        chapter_id
        for chapter_ids in by_path.values()
        for chapter_id in chapter_ids
    }
    if root_source_set != provenance_union:
        raise SourceChapterEnforcementError(
            "root sourceChapterIds must equal the union of fieldProvenance sourceChapterIds"
        )

    return by_path


def _collect_populated_leaf_paths(value: Any, path: str, paths: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _collect_populated_leaf_paths(item, f"{path}.{key}", paths)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_populated_leaf_paths(item, f"{path}[{index}]", paths)
        return
    if _is_populated_leaf(value):
        paths.append(path)


def _is_populated_leaf(value: Any) -> bool:
    if value is None or isinstance(value, (dict, list, tuple)):
        return False
    if isinstance(value, str):
        return bool(value)
    return True
