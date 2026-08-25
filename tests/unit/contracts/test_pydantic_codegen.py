"""AT-4: Pydantic generation from AT-1 / AT-2 / AT-3 canonical JSON Schemas."""

from __future__ import annotations

import importlib
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
    (
        "slide_spec/group_a/cover_01.schema.json",
        "slide_spec_group_a_cover_01.py",
        "Cover01SlideSpec",
    ),
    (
        "slide_spec/group_a/context_01.schema.json",
        "slide_spec_group_a_context_01.py",
        "Context01SlideSpec",
    ),
    (
        "slide_spec/group_a/problem_solution_01.schema.json",
        "slide_spec_group_a_problem_solution_01.py",
        "ProblemSolution01SlideSpec",
    ),
    (
        "slide_spec/group_a/scope_01.schema.json",
        "slide_spec_group_a_scope_01.py",
        "Scope01SlideSpec",
    ),
    (
        "slide_spec/group_a/requirements_matrix_01.schema.json",
        "slide_spec_group_a_requirements_matrix_01.py",
        "RequirementsMatrix01SlideSpec",
    ),
    (
        "slide_spec/group_b/process_flow_01.schema.json",
        "slide_spec_group_b_process_flow_01.py",
        "ProcessFlow01SlideSpec",
    ),
    (
        "slide_spec/group_b/timeline_01.schema.json",
        "slide_spec_group_b_timeline_01.py",
        "Timeline01SlideSpec",
    ),
    (
        "slide_spec/group_b/milestones_01.schema.json",
        "slide_spec_group_b_milestones_01.py",
        "Milestones01SlideSpec",
    ),
    (
        "slide_spec/group_b/team_fte_01.schema.json",
        "slide_spec_group_b_team_fte_01.py",
        "TeamFte01SlideSpec",
    ),
    (
        "slide_spec/group_c/architecture_01.schema.json",
        "slide_spec_group_c_architecture_01.py",
        "Architecture01SlideSpec",
    ),
    (
        "slide_spec/group_c/compliance_01.schema.json",
        "slide_spec_group_c_compliance_01.py",
        "Compliance01SlideSpec",
    ),
    (
        "slide_spec/group_c/success_metrics_01.schema.json",
        "slide_spec_group_c_success_metrics_01.py",
        "SuccessMetrics01SlideSpec",
    ),
    (
        "slide_spec/group_c/open_questions_01.schema.json",
        "slide_spec_group_c_open_questions_01.py",
        "OpenQuestions01SlideSpec",
    ),
    (
        "slide_spec/group_c/next_steps_01.schema.json",
        "slide_spec_group_c_next_steps_01.py",
        "NextSteps01SlideSpec",
    ),
]

GROUP_A_MODELS = [
    ("cover_01", "slide_spec_group_a_cover_01", "Cover01SlideSpec"),
    ("context_01", "slide_spec_group_a_context_01", "Context01SlideSpec"),
    (
        "problem_solution_01",
        "slide_spec_group_a_problem_solution_01",
        "ProblemSolution01SlideSpec",
    ),
    ("scope_01", "slide_spec_group_a_scope_01", "Scope01SlideSpec"),
    (
        "requirements_matrix_01",
        "slide_spec_group_a_requirements_matrix_01",
        "RequirementsMatrix01SlideSpec",
    ),
]

GROUP_B_MODELS = [
    ("process_flow_01", "slide_spec_group_b_process_flow_01", "ProcessFlow01SlideSpec"),
    ("timeline_01", "slide_spec_group_b_timeline_01", "Timeline01SlideSpec"),
    ("milestones_01", "slide_spec_group_b_milestones_01", "Milestones01SlideSpec"),
    ("team_fte_01", "slide_spec_group_b_team_fte_01", "TeamFte01SlideSpec"),
]

GROUP_C_MODELS = [
    ("architecture_01", "slide_spec_group_c_architecture_01", "Architecture01SlideSpec"),
    ("compliance_01", "slide_spec_group_c_compliance_01", "Compliance01SlideSpec"),
    (
        "success_metrics_01",
        "slide_spec_group_c_success_metrics_01",
        "SuccessMetrics01SlideSpec",
    ),
    (
        "open_questions_01",
        "slide_spec_group_c_open_questions_01",
        "OpenQuestions01SlideSpec",
    ),
    ("next_steps_01", "slide_spec_group_c_next_steps_01", "NextSteps01SlideSpec"),
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


def test_at4_generates_all_registered_modules() -> None:
    """Every canonical schema registered for Python codegen produces a module."""
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


@pytest.mark.parametrize("fixture_name,module_name,model_name", GROUP_A_MODELS)
@pytest.mark.parametrize("variant", ["minimal", "realistic"])
def test_group_a_fixture_validates_with_generated_pydantic_model(
    fixture_name: str, module_name: str, model_name: str, variant: str
) -> None:
    module = importlib.import_module(f"generated.python.contracts.{module_name}")
    model = getattr(module, model_name)
    fixture_path = FIXTURES_DIR / "slide_spec" / "group_a" / f"{fixture_name}.{variant}.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    generated = model.model_validate(payload)
    assert generated.layoutId == payload["layoutId"]


@pytest.mark.parametrize("fixture_name,module_name,model_name", GROUP_B_MODELS)
@pytest.mark.parametrize("variant", ["minimal", "realistic"])
def test_group_b_fixture_validates_with_generated_pydantic_model(
    fixture_name: str, module_name: str, model_name: str, variant: str
) -> None:
    module = importlib.import_module(f"generated.python.contracts.{module_name}")
    model = getattr(module, model_name)
    fixture_path = FIXTURES_DIR / "slide_spec" / "group_b" / f"{fixture_name}.{variant}.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    generated = model.model_validate(payload)
    assert generated.layoutId == payload["layoutId"]


@pytest.mark.parametrize("fixture_name,module_name,model_name", GROUP_C_MODELS)
def test_group_c_fixture_validates_with_generated_pydantic_model(
    fixture_name: str, module_name: str, model_name: str
) -> None:
    module = importlib.import_module(f"generated.python.contracts.{module_name}")
    model = getattr(module, model_name)
    fixture_path = FIXTURES_DIR / "slide_spec" / f"{fixture_name}.minimal.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    generated = model.model_validate(payload)
    assert generated.layoutId == payload["layoutId"]


@pytest.mark.parametrize("fixture_name,module_name,model_name", GROUP_A_MODELS)
def test_group_a_generated_model_rejects_wrong_layout_id(
    fixture_name: str, module_name: str, model_name: str
) -> None:
    module = importlib.import_module(f"generated.python.contracts.{module_name}")
    model = getattr(module, model_name)
    fixture_path = FIXTURES_DIR / "slide_spec" / "group_a" / f"{fixture_name}.minimal.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["layoutId"] = "ARCHITECTURE_01"
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("fixture_name,module_name,model_name", GROUP_A_MODELS)
def test_group_a_generated_model_rejects_unexpected_root_field(
    fixture_name: str, module_name: str, model_name: str
) -> None:
    module = importlib.import_module(f"generated.python.contracts.{module_name}")
    model = getattr(module, model_name)
    fixture_path = FIXTURES_DIR / "slide_spec" / "group_a" / f"{fixture_name}.minimal.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["color"] = "#00FF00"
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("fixture_name,module_name,model_name", GROUP_B_MODELS)
def test_group_b_generated_model_rejects_wrong_layout_id(
    fixture_name: str, module_name: str, model_name: str
) -> None:
    module = importlib.import_module(f"generated.python.contracts.{module_name}")
    model = getattr(module, model_name)
    fixture_path = FIXTURES_DIR / "slide_spec" / "group_b" / f"{fixture_name}.minimal.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["layoutId"] = "ARCHITECTURE_01"
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("fixture_name,module_name,model_name", GROUP_B_MODELS)
def test_group_b_generated_model_rejects_unexpected_root_field(
    fixture_name: str, module_name: str, model_name: str
) -> None:
    module = importlib.import_module(f"generated.python.contracts.{module_name}")
    model = getattr(module, model_name)
    fixture_path = FIXTURES_DIR / "slide_spec" / "group_b" / f"{fixture_name}.minimal.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["color"] = "#00FF00"
    with pytest.raises(ValidationError):
        model.model_validate(payload)


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
