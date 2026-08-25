"""AT-20: addSectionLabel() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addSectionLabel.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at20_add_section_label_file_exists() -> None:
    """Maps to AT-20 done-when: eyebrow-label component exists in design_system/components."""
    assert COMPONENT_TS.is_file(), f"expected addSectionLabel at {COMPONENT_TS}"


def test_at20_renderer_unit_checks() -> None:
    """Body typography from tokens, placeholder targeting, accent/inverse variants on all label masters."""
    result = _run_shell("npm run test:at20 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
