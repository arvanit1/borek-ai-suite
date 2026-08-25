"""AT-15: MASTER_COVER slide master tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MASTER_TS = ROOT / "apps" / "renderer" / "design_system" / "masters" / "MASTER_COVER.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at15_master_cover_file_exists() -> None:
    """Maps to AT-15 done-when: cover SlideMaster module exists in design_system/masters."""
    assert MASTER_TS.is_file(), f"expected MASTER_COVER at {MASTER_TS}"


def test_at15_renderer_unit_checks() -> None:
    """Cover title/subtitle/stat-badge regions, coverBackground, footer/slide-number from branding."""
    result = _run_shell("npm run test:at15 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
