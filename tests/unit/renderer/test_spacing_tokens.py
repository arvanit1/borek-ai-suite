"""AT-13: Borek spacing and grid token tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPACING_TS = ROOT / "apps" / "renderer" / "design_system" / "tokens" / "spacing.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at13_spacing_token_file_exists() -> None:
    """Maps to AT-13 done-when: spacing/grid tokens centralized in one renderer file."""
    assert SPACING_TS.is_file(), f"expected canonical spacing tokens at {SPACING_TS}"


def test_at13_renderer_unit_checks() -> None:
    """§16 margins/footer height, grid spacing tokens, no inline spacing in layouts/design_system."""
    result = _run_shell("npm run test:at13 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
