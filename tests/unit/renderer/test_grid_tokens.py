"""Grid spacing token tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GRID_TS = ROOT / "apps" / "renderer" / "design_system" / "tokens" / "grid.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_grid_token_file_exists() -> None:
    """Maps to v2 §16 design-system/grid.ts — column/row gaps derived from spacing."""
    assert GRID_TS.is_file(), f"expected canonical grid tokens at {GRID_TS}"


def test_grid_renderer_unit_checks() -> None:
    """Derived gaps, positive inches, no inline columnGap/rowGap in layouts/design_system."""
    result = _run_shell("npm run test:grid --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
