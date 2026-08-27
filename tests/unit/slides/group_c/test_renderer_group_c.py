"""MS-16 to MS-21: Group C renderer tests — all five layouts plus dispatcher registration."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RENDERER_LAYOUTS = ROOT / "apps" / "renderer" / "layouts" / "group_c"
DISPATCHER_TS = ROOT / "apps" / "renderer" / "layouts" / "dispatcher.ts"
STUBS_TS = ROOT / "apps" / "renderer" / "layouts" / "stubs.ts"

LAYOUT_TESTS = (
    ("MS-16", "renderArchitecture01.ts", "test:ms16"),
    ("MS-17", "renderCompliance01.ts", "test:ms17"),
    ("MS-18", "renderSuccessMetrics01.ts", "test:ms18"),
    ("MS-19", "renderOpenQuestions01.ts", "test:ms19"),
    ("MS-20", "renderNextSteps01.ts", "test:ms20"),
)


def _run_shell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, shell=True, text=True, capture_output=True)


def test_group_c_renderer_modules_exist() -> None:
    for _ticket, file_name, _script in LAYOUT_TESTS:
        path = RENDERER_LAYOUTS / file_name
        assert path.is_file(), f"expected renderer at {path}"
        assert (RENDERER_LAYOUTS / file_name.replace(".ts", ".test.ts")).is_file()


def test_ms16_architecture_renderer_checks() -> None:
    result = _run_shell("npm run test:ms16 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms17_compliance_renderer_checks() -> None:
    result = _run_shell("npm run test:ms17 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms18_success_metrics_renderer_checks() -> None:
    result = _run_shell("npm run test:ms18 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms19_open_questions_renderer_checks() -> None:
    result = _run_shell("npm run test:ms19 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms20_next_steps_renderer_checks() -> None:
    result = _run_shell("npm run test:ms20 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms21_group_c_layouts_are_registered() -> None:
    dispatcher = DISPATCHER_TS.read_text(encoding="utf-8")
    stubs = STUBS_TS.read_text(encoding="utf-8")
    for name in (
        "renderArchitecture01",
        "renderCompliance01",
        "renderSuccessMetrics01",
        "renderOpenQuestions01",
        "renderNextSteps01",
    ):
        assert f'from "./group_c/{name}.js"' in dispatcher or f"from './group_c/{name}.js'" in dispatcher
        assert f"{name}Stub" not in stubs
    result = _run_shell("npm run test:ms21 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
