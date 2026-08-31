"""JJ-20: Group B renderer tests — min/max content, special characters, both languages, long names."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RENDERER_LAYOUTS = ROOT / "apps" / "renderer" / "layouts" / "group_b"

LAYOUT_TESTS = (
    ("JJ-15", "renderProcessFlow01.ts", "test:jj15"),
    ("JJ-16", "renderTimeline01.ts", "test:jj16"),
    ("JJ-17", "renderMilestones01.ts", "test:jj17"),
    ("JJ-18", "renderTeamFte01.ts", "test:jj18"),
)


def _run_shell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=False, shell=True, text=True, capture_output=True)


def test_jj20_group_b_renderer_modules_exist() -> None:
    for _ticket, file_name, _script in LAYOUT_TESTS:
        path = RENDERER_LAYOUTS / file_name
        assert path.is_file(), f"expected renderer at {path}"
        test_path = RENDERER_LAYOUTS / file_name.replace(".ts", ".test.ts")
        assert test_path.is_file()
        source = test_path.read_text(encoding="utf-8")
        assert "minimalFixture" in source
        assert "maximumFixture" in source
        assert "englishFixture" in source
        assert "germanFixture" in source
        assert "specialLongFixture" in source
        assert "JJ20_SPECIAL" in source


def test_jj20_process_flow_renderer() -> None:
    result = _run_shell("npm run test:jj15 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_jj20_timeline_renderer() -> None:
    result = _run_shell("npm run test:jj16 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_jj20_milestones_renderer() -> None:
    result = _run_shell("npm run test:jj17 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_jj20_team_fte_renderer() -> None:
    result = _run_shell("npm run test:jj18 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
