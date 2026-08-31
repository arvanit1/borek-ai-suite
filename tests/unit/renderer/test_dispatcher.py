"""AT-33: renderer layout dispatcher tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DISPATCHER_TS = ROOT / "apps" / "renderer" / "layouts" / "dispatcher.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at33_dispatcher_file_exists() -> None:
    """Maps to AT-33 done-when: layout dispatcher skeleton exists."""
    assert DISPATCHER_TS.is_file(), f"expected dispatcher at {DISPATCHER_TS}"


def test_at33_renderer_unit_checks() -> None:
    """Registry routing, SSOT alignment, and UnsupportedLayoutError behavior."""
    result = _run_shell("npm run test:at33 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout


def test_jj19_group_b_layouts_are_registered() -> None:
    stubs = (ROOT / "apps" / "renderer" / "layouts" / "stubs.ts").read_text(encoding="utf-8")
    dispatcher = DISPATCHER_TS.read_text(encoding="utf-8")
    for name in ("renderProcessFlow01", "renderTimeline01", "renderMilestones01", "renderTeamFte01"):
        assert f'from "./group_b/{name}.js"' in dispatcher or f"from './group_b/{name}.js'" in dispatcher
        assert f"{name}Stub" not in stubs
    result = _run_shell("npm run test:jj19 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
