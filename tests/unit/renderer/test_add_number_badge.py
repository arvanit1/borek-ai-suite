"""AT-24: addNumberBadge() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addNumberBadge.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at24_add_number_badge_file_exists() -> None:
    """Maps to AT-24 done-when: numbered circle badge component exists."""
    assert COMPONENT_TS.is_file(), f"expected addNumberBadge at {COMPONENT_TS}"


def test_at24_renderer_unit_checks() -> None:
    """Primary fill, centered number typography, ellipse shape in pptx XML."""
    result = _run_shell("npm run test:at24 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
