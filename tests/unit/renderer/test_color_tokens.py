"""AT-11: Borek brand color token tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RENDERER_DIR = ROOT / "apps" / "renderer"
COLORS_TS = RENDERER_DIR / "design_system" / "tokens" / "colors.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at11_colors_token_file_exists() -> None:
    """Maps to AT-11 done-when: one file holds every brand color in the renderer."""
    assert COLORS_TS.is_file(), f"expected canonical color tokens at {COLORS_TS}"


def test_at11_renderer_unit_checks() -> None:
    """§16 palette, hex format, and no hardcoded hex in layouts + design_system (except colors.ts)."""
    result = _run_shell("npm run test:at11 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
