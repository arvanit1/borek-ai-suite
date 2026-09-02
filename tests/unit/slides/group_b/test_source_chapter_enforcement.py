"""JJ-9: Group B field-level provenance using the shared BT-14 validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.group_b_source_chapters import (
    GROUP_B_ALLOWED_CHAPTER_IDS,
    validate_group_b_field_provenance,
)
from services.validation.source_chapter_enforcement import (
    SourceChapterEnforcementError,
    populated_content_leaf_paths,
    validate_field_provenance,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_b"

FIXTURE_NAMES = {
    "PROCESS_FLOW_01": "process_flow_01.minimal.json",
    "TIMELINE_01": "timeline_01.minimal.json",
    "MILESTONES_01": "milestones_01.minimal.json",
    "TEAM_FTE_01": "team_fte_01.minimal.json",
}


def _payload(layout_id: str) -> dict:
    return json.loads((FIXTURE_DIR / FIXTURE_NAMES[layout_id]).read_text(encoding="utf-8"))


@pytest.mark.parametrize("layout_id", GROUP_B_ALLOWED_CHAPTER_IDS)
def test_jj9_valid_provenance_for_all_four_group_b_layouts(layout_id: str) -> None:
    payload = _payload(layout_id)
    provenance = validate_group_b_field_provenance(payload)
    assert set(provenance) == set(populated_content_leaf_paths(payload))
    assert set(payload["sourceChapterIds"]) == set(GROUP_B_ALLOWED_CHAPTER_IDS[layout_id])


def test_jj9_missing_field_provenance_fails() -> None:
    payload = _payload("TIMELINE_01")
    del payload["fieldProvenance"]
    with pytest.raises(SourceChapterEnforcementError, match="fieldProvenance"):
        validate_group_b_field_provenance(payload)


def test_jj9_missing_one_populated_nested_field_fails() -> None:
    payload = _payload("PROCESS_FLOW_01")
    payload["fieldProvenance"] = [
        entry
        for entry in payload["fieldProvenance"]
        if entry["path"] != "phases[0].description"
    ]
    with pytest.raises(SourceChapterEnforcementError, match=r"phases\[0\]\.description"):
        validate_group_b_field_provenance(payload)


def test_jj9_unknown_or_stale_paths_fail() -> None:
    payload = _payload("TEAM_FTE_01")
    payload["fieldProvenance"].append(
        {"path": "roles[99].role", "sourceChapterIds": ["10"]}
    )
    with pytest.raises(SourceChapterEnforcementError, match="does not resolve"):
        validate_group_b_field_provenance(payload)


def test_jj9_unknown_chapter_id_fails() -> None:
    payload = _payload("MILESTONES_01")
    payload["fieldProvenance"][0]["sourceChapterIds"] = ["99"]
    with pytest.raises(SourceChapterEnforcementError, match="non-existent Framework chapter"):
        validate_field_provenance(
            payload,
            real_chapter_ids=("10",),
            allowed_chapter_ids=("10",),
        )


def test_jj9_field_chapter_outside_layout_allowance_fails() -> None:
    payload = _payload("PROCESS_FLOW_01")
    payload["sourceChapterIds"].append("10")
    payload["fieldProvenance"][0]["sourceChapterIds"] = ["10"]
    with pytest.raises(SourceChapterEnforcementError, match="outside the layout"):
        validate_field_provenance(
            payload,
            real_chapter_ids=("2", "4", "10"),
            allowed_chapter_ids=("2", "4"),
        )


def test_jj9_root_must_equal_field_provenance_union() -> None:
    payload = _payload("PROCESS_FLOW_01")
    payload["fieldProvenance"] = [
        {**entry, "sourceChapterIds": ["2"]}
        for entry in payload["fieldProvenance"]
    ]
    with pytest.raises(SourceChapterEnforcementError, match="must equal the union"):
        validate_group_b_field_provenance(payload)


def test_jj9_optional_subtitle_requires_provenance_only_when_populated() -> None:
    payload = _payload("TIMELINE_01")
    validate_group_b_field_provenance(payload)

    payload["subtitle"] = "Confirm access before build"
    with pytest.raises(SourceChapterEnforcementError, match="subtitle"):
        validate_group_b_field_provenance(payload)

    payload["fieldProvenance"].append({"path": "subtitle", "sourceChapterIds": ["10"]})
    validate_group_b_field_provenance(payload)


def test_jj9_does_not_edit_shared_enforcement_module() -> None:
    source = (
        ROOT / "apps" / "api" / "services" / "validation" / "source_chapter_enforcement.py"
    ).read_text(encoding="utf-8")
    assert "PROCESS_FLOW_01" not in source
    assert "GROUP_B" not in source
    assert "validate_field_provenance" in source


def test_jj9_shared_validator_rejects_chapter_absent_from_root() -> None:
    payload = _payload("PROCESS_FLOW_01")
    payload["sourceChapterIds"] = ["2"]
    with pytest.raises(SourceChapterEnforcementError, match="absent from root"):
        validate_field_provenance(
            payload,
            real_chapter_ids=("2", "4"),
            allowed_chapter_ids=("2", "4"),
        )


def test_jj9_validation_does_not_mutate_payload() -> None:
    payload = _payload("TEAM_FTE_01")
    before = copy.deepcopy(payload)
    validate_group_b_field_provenance(payload)
    assert payload == before
