"""AT-4: Pydantic generation from AT-1 / AT-2 / AT-3 canonical JSON Schemas."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"
GENERATED_DIR = ROOT / "generated" / "python" / "contracts"

AT4_SCHEMA_OUTPUTS = [
    ("framework_object.schema.json", "framework_object.py", "FrameworkObject"),
    ("presentation_plan.schema.json", "presentation_plan.py", "PresentationPlan"),
    ("slide_spec/base.schema.json", "slide_spec_base.py", "SlideSpecBase"),
]


@pytest.fixture(scope="module", autouse=True)
def run_pydantic_codegen() -> None:
    """AT-4 generation step must succeed before model tests."""
    subprocess.run(
        [sys.executable, "scripts/generate_pydantic.py"],
        cwd=ROOT,
        check=True,
    )


@pytest.fixture(scope="module")
def framework_object_model():
    from generated.python.contracts.framework_object import FrameworkObject

    return FrameworkObject


@pytest.fixture(scope="module")
def presentation_plan_model():
    from generated.python.contracts.presentation_plan import PresentationPlan

    return PresentationPlan


@pytest.fixture(scope="module")
def slide_spec_base_model():
    from generated.python.contracts.slide_spec_base import SlideSpecBase

    return SlideSpecBase


def test_at4_generates_all_three_modules() -> None:
    """Maps to AT-4 done-when: valid Pydantic models from AT-1, AT-2, AT-3."""
    for _schema, output_name, _model_name in AT4_SCHEMA_OUTPUTS:
        assert (GENERATED_DIR / output_name).is_file(), f"missing generated module {output_name}"


def test_at4_generated_modules_import() -> None:
    import generated.python.contracts.framework_object as fo
    import generated.python.contracts.presentation_plan as pp
    import generated.python.contracts.slide_spec_base as ss

    assert fo.FrameworkObject is not None
    assert pp.PresentationPlan is not None
    assert ss.SlideSpecBase is not None


def test_framework_object_fixture_validates(framework_object_model) -> None:
    payload = json.loads((FIXTURES_DIR / "framework_object.minimal.json").read_text(encoding="utf-8"))
    obj = framework_object_model.model_validate(payload)
    assert obj.schema_version == "1.0"
    assert len(obj.chapters) == 14


def test_framework_object_rejects_invalid_status(framework_object_model) -> None:
    payload = json.loads((FIXTURES_DIR / "framework_object.minimal.json").read_text(encoding="utf-8"))
    payload["status"] = "approved"
    with pytest.raises(ValidationError):
        framework_object_model.model_validate(payload)


def test_presentation_plan_fixture_validates(presentation_plan_model) -> None:
    payload = json.loads((FIXTURES_DIR / "presentation_plan.minimal.json").read_text(encoding="utf-8"))
    plan = presentation_plan_model.model_validate(payload)
    assert plan.schema_version == "1.0"
    assert len(plan.slides) >= 1


def test_presentation_plan_rejects_missing_order(presentation_plan_model) -> None:
    payload = json.loads((FIXTURES_DIR / "presentation_plan.minimal.json").read_text(encoding="utf-8"))
    slides = [dict(s) for s in payload["slides"]]
    del slides[0]["order"]
    payload["slides"] = slides
    with pytest.raises(ValidationError):
        presentation_plan_model.model_validate(payload)


def test_slide_spec_base_fixture_validates(slide_spec_base_model) -> None:
    payload = json.loads(
        (FIXTURES_DIR / "slide_spec" / "architecture_01.minimal.json").read_text(encoding="utf-8")
    )
    spec = slide_spec_base_model.model_validate(payload)
    assert spec.layoutId.value == "ARCHITECTURE_01"
    assert len(spec.sourceChapterIds) == 2


def test_slide_spec_base_allows_layout_specific_extra_fields(slide_spec_base_model) -> None:
    payload = json.loads(
        (FIXTURES_DIR / "slide_spec" / "architecture_01.minimal.json").read_text(encoding="utf-8")
    )
    spec = slide_spec_base_model.model_validate(payload)
    assert spec.model_extra is not None
    assert "components" in spec.model_extra


def test_slide_spec_base_rejects_empty_source_chapter_ids(slide_spec_base_model) -> None:
    payload = json.loads(
        (FIXTURES_DIR / "slide_spec" / "architecture_01.minimal.json").read_text(encoding="utf-8")
    )
    payload["sourceChapterIds"] = []
    with pytest.raises(ValidationError):
        slide_spec_base_model.model_validate(payload)


def test_regeneration_is_deterministic_enough_for_ci() -> None:
    """No manual edits: re-running codegen keeps importable modules."""
    before = {
        name: (GENERATED_DIR / name).read_text(encoding="utf-8")
        for _, name, _ in AT4_SCHEMA_OUTPUTS
    }
    subprocess.run([sys.executable, "scripts/generate_pydantic.py"], cwd=ROOT, check=True)
    after = {
        name: (GENERATED_DIR / name).read_text(encoding="utf-8")
        for _, name, _ in AT4_SCHEMA_OUTPUTS
    }
    for module_name in before:
        assert before[module_name] == after[module_name]
