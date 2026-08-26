"""MS-11: Group C field-level provenance using the shared BT-14 validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from services.slides.group_c_source_chapters import (
    GROUP_C_ALLOWED_CHAPTER_IDS,
    validate_group_c_field_provenance,
)
from services.validation.source_chapter_enforcement import (
    SourceChapterEnforcementError,
    populated_content_leaf_paths,
    validate_field_provenance,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = ROOT / "packages" / "contracts" / "fixtures" / "slide_spec"

FIXTURE_NAMES = {
    "ARCHITECTURE_01": "architecture_01.minimal.json",
    "COMPLIANCE_01": "compliance_01.minimal.json",
    "SUCCESS_METRICS_01": "success_metrics_01.minimal.json",
    "OPEN_QUESTIONS_01": "open_questions_01.minimal.json",
    "NEXT_STEPS_01": "next_steps_01.minimal.json",
}


def _payload(layout_id: str) -> dict:
    return json.loads((FIXTURE_DIR / FIXTURE_NAMES[layout_id]).read_text(encoding="utf-8"))


@pytest.mark.parametrize("layout_id", GROUP_C_ALLOWED_CHAPTER_IDS)
def test_ms11_valid_provenance_for_all_five_group_c_layouts(layout_id: str) -> None:
    payload = _payload(layout_id)
    provenance = validate_group_c_field_provenance(payload)
    assert set(provenance) == set(populated_content_leaf_paths(payload))
    assert payload["sourceChapterIds"] == list(GROUP_C_ALLOWED_CHAPTER_IDS[layout_id])


def test_ms11_missing_field_provenance_fails() -> None:
    payload = _payload("COMPLIANCE_01")
    del payload["fieldProvenance"]
    with pytest.raises(SourceChapterEnforcementError, match="fieldProvenance"):
        validate_group_c_field_provenance(payload)


def test_ms11_missing_one_populated_nested_field_fails() -> None:
    payload = _payload("ARCHITECTURE_01")
    payload["fieldProvenance"] = [
        entry
        for entry in payload["fieldProvenance"]
        if entry["path"] != "components[0].description"
    ]
    with pytest.raises(SourceChapterEnforcementError, match=r"components\[0\]\.description"):
        validate_group_c_field_provenance(payload)


def test_ms11_unknown_or_stale_paths_fail() -> None:
    payload = _payload("COMPLIANCE_01")
    payload["fieldProvenance"].append(
        {"path": "items[99].text", "sourceChapterIds": ["8"]}
    )
    with pytest.raises(SourceChapterEnforcementError, match="does not resolve"):
        validate_group_c_field_provenance(payload)


def test_ms11_field_chapter_outside_layout_allowance_fails() -> None:
    payload = _payload("ARCHITECTURE_01")
    payload["sourceChapterIds"].append("8")
    payload["fieldProvenance"][0]["sourceChapterIds"] = ["8"]
    with pytest.raises(SourceChapterEnforcementError, match="outside the layout"):
        validate_field_provenance(
            payload,
            real_chapter_ids=("6", "7", "8"),
            allowed_chapter_ids=("6", "7"),
        )


def test_ms11_root_must_equal_field_provenance_union() -> None:
    payload = _payload("SUCCESS_METRICS_01")
    payload["fieldProvenance"] = [
        {**entry, "sourceChapterIds": ["3"]}
        for entry in payload["fieldProvenance"]
    ]
    with pytest.raises(SourceChapterEnforcementError, match="must equal the union"):
        validate_group_c_field_provenance(payload)


def test_ms11_optional_subtitle_requires_provenance_only_when_populated() -> None:
    payload = _payload("COMPLIANCE_01")
    validate_group_c_field_provenance(payload)

    payload["subtitle"] = "Mailbox stays read-only"
    with pytest.raises(SourceChapterEnforcementError, match="subtitle"):
        validate_group_c_field_provenance(payload)

    payload["fieldProvenance"].append({"path": "subtitle", "sourceChapterIds": ["8"]})
    validate_group_c_field_provenance(payload)


def test_ms11_does_not_edit_shared_enforcement_module() -> None:
    source = (
        ROOT / "apps" / "api" / "services" / "validation" / "source_chapter_enforcement.py"
    ).read_text(encoding="utf-8")
    assert "ARCHITECTURE_01" not in source
    assert "GROUP_C" not in source
    assert "validate_field_provenance" in source


def test_ms11_shared_validator_rejects_chapter_absent_from_root() -> None:
    payload = _payload("ARCHITECTURE_01")
    payload["sourceChapterIds"] = ["6"]
    with pytest.raises(SourceChapterEnforcementError, match="absent from root"):
        validate_field_provenance(
            payload,
            real_chapter_ids=("6", "7"),
            allowed_chapter_ids=("6", "7"),
        )


def test_ms11_validation_does_not_mutate_payload() -> None:
    payload = _payload("OPEN_QUESTIONS_01")
    before = copy.deepcopy(payload)
    validate_group_c_field_provenance(payload)
    assert payload == before
