"""AT-18: MASTER_CLOSING slide master tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MASTER_TS = ROOT / "apps" / "renderer" / "design_system" / "masters" / "MASTER_CLOSING.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at18_master_closing_file_exists() -> None:
    """Maps to AT-18 done-when: closing SlideMaster module exists in design_system/masters."""
    assert MASTER_TS.is_file(), f"expected MASTER_CLOSING at {MASTER_TS}"


def test_at18_renderer_unit_checks() -> None:
    """Dark background, checklist/steps regions, NEXT_STEPS_01 layout id, footer/slide-number from branding."""
    result = _run_shell("npm run test:at18 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
