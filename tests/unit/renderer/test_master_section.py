"""AT-16: MASTER_SECTION slide master tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MASTER_TS = ROOT / "apps" / "renderer" / "design_system" / "masters" / "MASTER_SECTION.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at16_master_section_file_exists() -> None:
    """Maps to AT-16 done-when: section-divider SlideMaster module exists in design_system/masters."""
    assert MASTER_TS.is_file(), f"expected MASTER_SECTION at {MASTER_TS}"


def test_at16_renderer_unit_checks() -> None:
    """Section label/title regions, light background, footer/slide-number from branding."""
    result = _run_shell("npm run test:at16 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
