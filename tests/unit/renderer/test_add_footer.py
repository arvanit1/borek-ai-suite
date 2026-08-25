"""AT-21: addFooter() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addFooter.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at21_add_footer_file_exists() -> None:
    """Maps to AT-21 done-when: footer component exists in design_system/components."""
    assert COMPONENT_TS.is_file(), f"expected addFooter at {COMPONENT_TS}"


def test_at21_renderer_unit_checks() -> None:
    """Muted footer typography from branding tokens, consistent across all master types."""
    result = _run_shell("npm run test:at21 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
