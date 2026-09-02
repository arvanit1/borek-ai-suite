"""AT-5: TypeScript generation from AT-1 / AT-2 / AT-3 canonical JSON Schemas."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"
GENERATED_DIR = ROOT / "generated" / "typescript" / "contracts"
TS_TEST_DIR = ROOT / "tests" / "typescript"
RENDERER_DIR = ROOT / "apps" / "renderer"

AT5_SCHEMA_OUTPUTS = [
    ("framework_object.schema.json", "framework_object.ts", "FrameworkObject"),
    ("presentation_plan.schema.json", "presentation_plan.ts", "PresentationPlan"),
    ("slide_spec/base.schema.json", "slide_spec_base.ts", "SlideSpecBase"),
    (
        "slide_spec/group_a/cover_01.schema.json",
        "slide_spec_group_a_cover_01.ts",
        "Cover01SlideSpec",
    ),
    (
        "slide_spec/group_a/context_01.schema.json",
        "slide_spec_group_a_context_01.ts",
        "Context01SlideSpec",
    ),
    (
        "slide_spec/group_a/problem_solution_01.schema.json",
        "slide_spec_group_a_problem_solution_01.ts",
        "ProblemSolution01SlideSpec",
    ),
    (
        "slide_spec/group_a/scope_01.schema.json",
        "slide_spec_group_a_scope_01.ts",
        "Scope01SlideSpec",
    ),
    (
        "slide_spec/group_a/requirements_matrix_01.schema.json",
        "slide_spec_group_a_requirements_matrix_01.ts",
        "RequirementsMatrix01SlideSpec",
    ),
    (
        "slide_spec/summary/executive_summary_01.schema.json",
        "slide_spec_summary_executive_summary_01.ts",
        "ExecutiveSummary01SlideSpec",
    ),
    (
        "slide_spec/group_b/process_flow_01.schema.json",
        "slide_spec_group_b_process_flow_01.ts",
        "ProcessFlow01SlideSpec",
    ),
    (
        "slide_spec/group_b/timeline_01.schema.json",
        "slide_spec_group_b_timeline_01.ts",
        "Timeline01SlideSpec",
    ),
    (
        "slide_spec/group_b/milestones_01.schema.json",
        "slide_spec_group_b_milestones_01.ts",
        "Milestones01SlideSpec",
    ),
    (
        "slide_spec/group_b/team_fte_01.schema.json",
        "slide_spec_group_b_team_fte_01.ts",
        "TeamFte01SlideSpec",
    ),
    (
        "slide_spec/group_c/architecture_01.schema.json",
        "slide_spec_group_c_architecture_01.ts",
        "Architecture01SlideSpec",
    ),
    (
        "slide_spec/group_c/compliance_01.schema.json",
        "slide_spec_group_c_compliance_01.ts",
        "Compliance01SlideSpec",
    ),
    (
        "slide_spec/group_c/success_metrics_01.schema.json",
        "slide_spec_group_c_success_metrics_01.ts",
        "SuccessMetrics01SlideSpec",
    ),
    (
        "slide_spec/group_c/open_questions_01.schema.json",
        "slide_spec_group_c_open_questions_01.ts",
        "OpenQuestions01SlideSpec",
    ),
    (
        "slide_spec/group_c/next_steps_01.schema.json",
        "slide_spec_group_c_next_steps_01.ts",
        "NextSteps01SlideSpec",
    ),
]


def _run_shell(command: str) -> None:
    """Run npm/npx on Windows (requires shell=True)."""
    subprocess.run(command, cwd=ROOT, check=True, shell=True)


@pytest.fixture(scope="module", autouse=True)
def run_typescript_codegen() -> None:
    """AT-5 generation step must succeed before type tests."""
    subprocess.run(["node", "scripts/generate_typescript.js"], cwd=ROOT, check=True)


def test_at5_generates_all_registered_modules() -> None:
    """Every canonical schema registered for TypeScript codegen produces a module."""
    for _schema, output_name, _export_name in AT5_SCHEMA_OUTPUTS:
        assert (GENERATED_DIR / output_name).is_file(), f"missing generated module {output_name}"
    assert (GENERATED_DIR / "index.ts").is_file(), "missing generated barrel index.ts"


def test_at5_framework_object_chapters_are_not_never() -> None:
    """json-schema-to-typescript bug: prefixItems becomes never[] unless patched."""
    source = (GENERATED_DIR / "framework_object.ts").read_text(encoding="utf-8")
    assert "chapters: never[]" not in source
    assert "chapters: FrameworkObjectChapters;" in source
    assert "export type FrameworkObjectChapters =" in source
    assert "export type ChapterAtIndex0 =" in source
    assert "export type ChapterAtIndex13 =" in source


def test_at5_chapter_tuple_matches_registry() -> None:
    registry = json.loads((CONTRACTS_DIR / "chapter_registry.json").read_text(encoding="utf-8"))
    source = (GENERATED_DIR / "framework_object.ts").read_text(encoding="utf-8")
    for index, chapter in enumerate(registry["chapters"]):
        assert f'chapter_id: "{chapter["chapter_id"]}"' in source
        assert f'title: {json.dumps(chapter["title"])}' in source
        assert f"ChapterAtIndex{index}" in source


def test_at5_barrel_avoids_duplicate_layout_id_exports() -> None:
    index_source = (GENERATED_DIR / "index.ts").read_text(encoding="utf-8")
    assert 'export * from "./framework_object"' in index_source
    assert 'from "./slide_spec_base"' in index_source
    assert "ChapterId" in index_source
    assert "FieldProvenanceEntry" in index_source
    assert "SlideSpecBase" in index_source
    assert index_source.count("LayoutId") == 1
    assert 'export type { Cover01SlideSpec } from "./slide_spec_group_a_cover_01"' in index_source
    assert 'export type { Context01SlideSpec } from "./slide_spec_group_a_context_01"' in index_source
    assert (
        'export type { ProblemSolution01SlideSpec } from "./slide_spec_group_a_problem_solution_01"'
        in index_source
    )
    assert 'export type { Scope01SlideSpec } from "./slide_spec_group_a_scope_01"' in index_source
    assert (
        'export type { RequirementsMatrix01SlideSpec } '
        'from "./slide_spec_group_a_requirements_matrix_01"'
    in index_source
    )
    assert (
        'export type { ExecutiveSummary01SlideSpec } '
        'from "./slide_spec_summary_executive_summary_01"'
        in index_source
    )
    assert (
        'export type { ProcessFlow01SlideSpec } from "./slide_spec_group_b_process_flow_01"'
        in index_source
    )
    assert 'export type { Timeline01SlideSpec } from "./slide_spec_group_b_timeline_01"' in index_source
    assert (
        'export type { Milestones01SlideSpec } from "./slide_spec_group_b_milestones_01"'
        in index_source
    )
    assert 'export type { TeamFte01SlideSpec } from "./slide_spec_group_b_team_fte_01"' in index_source
    assert (
        'export type { Architecture01SlideSpec } from "./slide_spec_group_c_architecture_01"'
        in index_source
    )
    assert (
        'export type { Compliance01SlideSpec } from "./slide_spec_group_c_compliance_01"'
        in index_source
    )
    assert (
        'export type { SuccessMetrics01SlideSpec } '
        'from "./slide_spec_group_c_success_metrics_01"'
        in index_source
    )
    assert (
        'export type { OpenQuestions01SlideSpec } '
        'from "./slide_spec_group_c_open_questions_01"'
        in index_source
    )
    assert (
        'export type { NextSteps01SlideSpec } from "./slide_spec_group_c_next_steps_01"'
        in index_source
    )


def test_at5_fixture_typecheck_passes() -> None:
    """Contract fixtures must assign to generated interfaces under strict TypeScript."""
    tsconfig = TS_TEST_DIR / "tsconfig.json"
    _run_shell(f'npx tsc --noEmit -p "{tsconfig}"')


def test_at5_renderer_consumes_generated_types() -> None:
    """Maps to AT-5 done-when: types are used by the renderer service."""
    _run_shell("npm run typecheck --workspace borek-renderer")


def test_regeneration_is_deterministic_enough_for_ci() -> None:
    """No manual edits: re-running codegen keeps stable TypeScript modules."""
    before = {
        name: (GENERATED_DIR / name).read_text(encoding="utf-8")
        for _, name, _ in AT5_SCHEMA_OUTPUTS
    }
    before["index.ts"] = (GENERATED_DIR / "index.ts").read_text(encoding="utf-8")
    subprocess.run(["node", "scripts/generate_typescript.js"], cwd=ROOT, check=True)
    after = {
        name: (GENERATED_DIR / name).read_text(encoding="utf-8")
        for _, name, _ in AT5_SCHEMA_OUTPUTS
    }
    after["index.ts"] = (GENERATED_DIR / "index.ts").read_text(encoding="utf-8")
    for module_name in before:
        assert before[module_name] == after[module_name]
