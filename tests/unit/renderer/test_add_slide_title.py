"""AT-19: addSlideTitle() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addSlideTitle.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at19_add_slide_title_file_exists() -> None:
    """Maps to AT-19 done-when: reusable title component exists in design_system/components."""
    assert COMPONENT_TS.is_file(), f"expected addSlideTitle at {COMPONENT_TS}"


def test_at19_renderer_unit_checks() -> None:
    """Heading typography from tokens, placeholder targeting, light/dark variants on all title masters."""
    result = _run_shell("npm run test:at19 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
