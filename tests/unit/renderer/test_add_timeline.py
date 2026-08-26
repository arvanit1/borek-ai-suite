"""AT-28: addTimeline() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addTimeline.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at28_add_timeline_file_exists() -> None:
    """Maps to AT-28 done-when: timeline bar component exists."""
    assert COMPONENT_TS.is_file(), f"expected addTimeline at {COMPONENT_TS}"


def test_at28_renderer_unit_checks() -> None:
    """Week-proportional segments, milestone week mapping, token styling in pptx XML."""
    result = _run_shell("npm run test:at28 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
