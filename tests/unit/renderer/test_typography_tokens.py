"""AT-12: Borek typography token tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TYPOGRAPHY_TS = ROOT / "apps" / "renderer" / "design_system" / "tokens" / "typography.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at12_typography_token_file_exists() -> None:
    """Maps to AT-12 done-when: one file holds typography tokens for the renderer."""
    assert TYPOGRAPHY_TS.is_file(), f"expected canonical typography tokens at {TYPOGRAPHY_TS}"


def test_at12_renderer_unit_checks() -> None:
    """§16 font families, default size tokens, and no inline font styling in layouts/design_system."""
    result = _run_shell("npm run test:at12 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
