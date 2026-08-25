"""Border token tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BORDERS_TS = ROOT / "apps" / "renderer" / "design_system" / "tokens" / "borders.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_borders_token_file_exists() -> None:
    """Maps to v2 §16 design-system/borders.ts — card radius and divider/card line weights."""
    assert BORDERS_TS.is_file(), f"expected canonical border tokens at {BORDERS_TS}"


def test_borders_renderer_unit_checks() -> None:
    """Border color from BorekColors, derived radius, separate lineWidthPt tokens, CI guard."""
    result = _run_shell("npm run test:borders --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
