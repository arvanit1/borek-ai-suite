"""AT-32: addMilestone() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addMilestone.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at32_add_milestone_file_exists() -> None:
    """Maps to AT-32 done-when: milestone-marker component exists."""
    assert COMPONENT_TS.is_file(), f"expected addMilestone at {COMPONENT_TS}"


def test_at32_renderer_unit_checks() -> None:
    """Diamond marker, label, optional date, and token-derived sizing in pptx XML."""
    result = _run_shell("npm run test:at32 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
