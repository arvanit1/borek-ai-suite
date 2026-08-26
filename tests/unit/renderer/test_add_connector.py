"""AT-30: addConnector() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addConnector.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at30_add_connector_file_exists() -> None:
    """Maps to AT-30 done-when: line/connector component exists."""
    assert COMPONENT_TS.is_file(), f"expected addConnector at {COMPONENT_TS}"


def test_at30_renderer_unit_checks() -> None:
    """Default border color/width and line shape in pptx XML."""
    result = _run_shell("npm run test:at30 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
