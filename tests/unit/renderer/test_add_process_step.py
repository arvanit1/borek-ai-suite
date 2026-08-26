"""AT-31: addProcessStep() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addProcessStep.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at31_add_process_step_file_exists() -> None:
    """Maps to AT-31 done-when: numbered process-step component exists."""
    assert COMPONENT_TS.is_file(), f"expected addProcessStep at {COMPONENT_TS}"


def test_at31_renderer_unit_checks() -> None:
    """Badge, title, description, and bordered step block in pptx XML."""
    result = _run_shell("npm run test:at31 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
