"""AT-17: MASTER_CONTENT slide master tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MASTER_TS = ROOT / "apps" / "renderer" / "design_system" / "masters" / "MASTER_CONTENT.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at17_master_content_file_exists() -> None:
    """Maps to AT-17 done-when: standard content SlideMaster module exists in design_system/masters."""
    assert MASTER_TS.is_file(), f"expected MASTER_CONTENT at {MASTER_TS}"


def test_at17_renderer_unit_checks() -> None:
    """Section label/title header band, light background, majority layout ids, footer/slide-number from branding."""
    result = _run_shell("npm run test:at17 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
