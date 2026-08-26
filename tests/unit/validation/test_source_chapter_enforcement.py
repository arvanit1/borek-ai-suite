"""BT-14: shared field-level source chapter enforcement tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.validation.source_chapter_enforcement import (
    SourceChapterEnforcementError,
    populated_content_leaf_paths,
    validate_field_provenance,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"

ALLOWED_BY_FIXTURE = {
    "cover_01": ("1",),
    "context_01": ("1", "2"),
    "problem_solution_01": ("2", "4"),
    "scope_01": ("3", "5"),
    "requirements_matrix_01": ("5",),
}


def _fixture(name: str, variant: str = "minimal") -> dict:
    return json.loads(
        (FIXTURE_DIR / f"{name}.{variant}.json").read_text(encoding="utf-8")
    )


def _validate(payload: dict, allowed: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    return validate_field_provenance(
        payload,
        real_chapter_ids=allowed,
        allowed_chapter_ids=allowed,
    )


@pytest.mark.parametrize("fixture_name", ALLOWED_BY_FIXTURE)
def test_bt14_valid_provenance_for_all_five_group_a_layouts(fixture_name: str) -> None:
    payload = _fixture(fixture_name, "realistic")

    provenance = _validate(payload, ALLOWED_BY_FIXTURE[fixture_name])

    assert set(provenance) == set(populated_content_leaf_paths(payload))


def test_bt14_missing_field_provenance_fails() -> None:
    payload = _fixture("context_01")
    del payload["fieldProvenance"]

    with pytest.raises(SourceChapterEnforcementError, match="fieldProvenance"):
        _validate(payload, ("1", "2"))


def test_bt14_missing_one_populated_nested_field_fails() -> None:
    payload = _fixture("context_01")
    payload["fieldProvenance"] = [
        entry
        for entry in payload["fieldProvenance"]
        if entry["path"] != "problem.description"
    ]

    with pytest.raises(SourceChapterEnforcementError, match="problem.description"):
        _validate(payload, ("1", "2"))


def test_bt14_individual_array_item_coverage_is_required() -> None:
    payload = _fixture("scope_01", "realistic")
    payload["fieldProvenance"] = [
        entry
        for entry in payload["fieldProvenance"]
        if entry["path"] != "included[3]"
    ]

    with pytest.raises(SourceChapterEnforcementError, match=r"included\[3\]"):
        _validate(payload, ("3", "5"))


def test_bt14_duplicate_paths_fail() -> None:
    payload = _fixture("cover_01")
    payload["fieldProvenance"].append(copy.deepcopy(payload["fieldProvenance"][0]))

    with pytest.raises(SourceChapterEnforcementError, match="Duplicate"):
        _validate(payload, ("1",))


def test_bt14_duplicate_field_source_chapter_ids_fail() -> None:
    payload = _fixture("cover_01")
    payload["fieldProvenance"][0]["sourceChapterIds"] = ["1", "1"]

    with pytest.raises(SourceChapterEnforcementError, match="must be unique"):
        _validate(payload, ("1",))


@pytest.mark.parametrize("path", ["unknown.path", "statBadges[99].value"])
def test_bt14_unknown_or_stale_paths_fail(path: str) -> None:
    payload = _fixture("cover_01")
    payload["fieldProvenance"].append(
        {"path": path, "sourceChapterIds": ["1"]}
    )

    with pytest.raises(SourceChapterEnforcementError, match="does not resolve"):
        _validate(payload, ("1",))


def test_bt14_path_that_resolves_to_an_object_is_not_a_content_leaf() -> None:
    payload = _fixture("context_01")
    payload["fieldProvenance"].append(
        {"path": "problem", "sourceChapterIds": ["2"]}
    )

    with pytest.raises(SourceChapterEnforcementError, match="not a populated content leaf"):
        _validate(payload, ("1", "2"))


def test_bt14_empty_field_source_chapter_ids_fail() -> None:
    payload = _fixture("cover_01")
    payload["fieldProvenance"][0]["sourceChapterIds"] = []

    with pytest.raises(SourceChapterEnforcementError, match="non-empty"):
        _validate(payload, ("1",))


def test_bt14_invalid_real_chapter_id_fails() -> None:
    payload = _fixture("cover_01")
    payload["sourceChapterIds"] = ["1", "99"]
    payload["fieldProvenance"][0]["sourceChapterIds"] = ["99"]

    with pytest.raises(SourceChapterEnforcementError, match="non-existent"):
        validate_field_provenance(
            payload,
            real_chapter_ids=("1",),
            allowed_chapter_ids=("1", "99"),
        )


def test_bt14_chapter_outside_layout_allowance_fails() -> None:
    payload = _fixture("scope_01")
    payload["sourceChapterIds"].append("13")
    payload["fieldProvenance"][0]["sourceChapterIds"] = ["13"]

    with pytest.raises(SourceChapterEnforcementError, match="outside the layout"):
        validate_field_provenance(
            payload,
            real_chapter_ids=("3", "5", "13"),
            allowed_chapter_ids=("3", "5"),
        )


def test_bt14_field_chapter_absent_from_root_fails() -> None:
    payload = _fixture("scope_01")
    payload["sourceChapterIds"] = ["3"]

    with pytest.raises(SourceChapterEnforcementError, match="absent from root"):
        _validate(payload, ("3", "5"))


def test_bt14_root_must_equal_field_provenance_union() -> None:
    payload = _fixture("scope_01")
    payload["fieldProvenance"] = [
        {**entry, "sourceChapterIds": ["3"]}
        for entry in payload["fieldProvenance"]
    ]

    with pytest.raises(SourceChapterEnforcementError, match="must equal the union"):
        _validate(payload, ("3", "5"))


def test_bt14_optional_content_requires_provenance_only_when_populated() -> None:
    payload = _fixture("context_01")
    _validate(payload, ("1", "2"))

    payload["subtitle"] = "A grounded optional subtitle"
    with pytest.raises(SourceChapterEnforcementError, match="subtitle"):
        _validate(payload, ("1", "2"))

    payload["fieldProvenance"].append(
        {"path": "subtitle", "sourceChapterIds": ["1"]}
    )
    _validate(payload, ("1", "2"))


def test_bt14_paraphrase_is_accepted_when_structurally_attributed() -> None:
    payload = _fixture("context_01")
    payload["problem"]["description"] = (
        "A concise paraphrase whose exact wording need not occur in the Framework."
    )

    _validate(payload, ("1", "2"))


def test_bt14_metadata_fields_are_exempt() -> None:
    payload = _fixture("cover_01")
    paths = set(populated_content_leaf_paths(payload))

    assert "schema_version" not in paths
    assert "layoutId" not in paths
    assert "slideId" not in paths
    assert "sourceChapterIds[0]" not in paths
    assert not any(path.startswith("fieldProvenance") for path in paths)
