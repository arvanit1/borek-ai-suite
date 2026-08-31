"""MS-22: Group C renderer edges — min/max, special characters, both languages, long names."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RENDERER_LAYOUTS = ROOT / "apps" / "renderer" / "layouts" / "group_c"

LAYOUT_TESTS = (
    ("MS-16", "renderArchitecture01.ts", "test:ms16"),
    ("MS-17", "renderCompliance01.ts", "test:ms17"),
    ("MS-18", "renderSuccessMetrics01.ts", "test:ms18"),
    ("MS-19", "renderOpenQuestions01.ts", "test:ms19"),
    ("MS-20", "renderNextSteps01.ts", "test:ms20"),
)


def _run_shell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, shell=True, text=True, capture_output=True)


def test_ms22_group_c_renderer_edge_modules_exist() -> None:
    for _ticket, file_name, _script in LAYOUT_TESTS:
        path = RENDERER_LAYOUTS / file_name
        assert path.is_file(), f"expected renderer at {path}"
        test_path = RENDERER_LAYOUTS / file_name.replace(".ts", ".test.ts")
        assert test_path.is_file(), f"expected edge coverage at {test_path}"
        source = test_path.read_text(encoding="utf-8")
        assert "minimumFixture" in source or "twoNode" in source
        assert "maximumFixture" in source
        assert "Ä" in source or "ß" in source or "&amp;" in source


def test_ms22_architecture_edges() -> None:
    result = _run_shell("npm run test:ms16 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms22_compliance_edges() -> None:
    result = _run_shell("npm run test:ms17 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms22_success_metrics_edges() -> None:
    result = _run_shell("npm run test:ms18 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms22_open_questions_edges() -> None:
    result = _run_shell("npm run test:ms19 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms22_next_steps_edges() -> None:
    result = _run_shell("npm run test:ms20 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_ms22_workspace_script_runs_all_five() -> None:
    result = _run_shell("npm run test:ms22 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
