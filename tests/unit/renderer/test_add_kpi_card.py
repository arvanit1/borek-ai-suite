"""AT-23: addKpiCard() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addKpiCard.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at23_add_kpi_card_file_exists() -> None:
    """Maps to AT-23 done-when: stat/value card component exists."""
    assert COMPONENT_TS.is_file(), f"expected addKpiCard at {COMPONENT_TS}"


def test_at23_renderer_unit_checks() -> None:
    """Value+unit+label typography, variant colors, rounded shape in cover-slide pptx XML."""
    result = _run_shell("npm run test:at23 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
