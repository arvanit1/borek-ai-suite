"""AT-25: addBulletList() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addBulletList.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at25_add_bullet_list_file_exists() -> None:
    """Maps to AT-25 done-when: standard bullet list component exists."""
    assert COMPONENT_TS.is_file(), f"expected addBulletList at {COMPONENT_TS}"


def test_at25_renderer_unit_checks() -> None:
    """Grid-derived spacing, body typography, native bullet markup in pptx XML."""
    result = _run_shell("npm run test:at25 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
