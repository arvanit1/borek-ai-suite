"""AT-22: addContentCard() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addContentCard.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at22_add_content_card_file_exists() -> None:
    """Maps to AT-22 done-when: generic title+description card component exists."""
    assert COMPONENT_TS.is_file(), f"expected addContentCard at {COMPONENT_TS}"


def test_at22_renderer_unit_checks() -> None:
    """Card border/fill from tokens, title+description typography, rounded shape in pptx XML."""
    result = _run_shell("npm run test:at22 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
