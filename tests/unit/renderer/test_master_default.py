"""AT-14: MASTER_DEFAULT slide master tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MASTER_TS = ROOT / "apps" / "renderer" / "design_system" / "masters" / "MASTER_DEFAULT.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at14_master_default_file_exists() -> None:
    """Maps to AT-14 done-when: base SlideMaster module exists in design_system/masters."""
    assert MASTER_TS.is_file(), f"expected MASTER_DEFAULT at {MASTER_TS}"


def test_at14_renderer_unit_checks() -> None:
    """Logo/footer/page-number placeholders positioned per design tokens; pptx registers master."""
    result = _run_shell("npm run test:at14 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
