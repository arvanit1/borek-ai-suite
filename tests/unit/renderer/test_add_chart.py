"""AT-27: addChart() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addChart.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at27_add_chart_file_exists() -> None:
    """Maps to AT-27 done-when: native chart component exists."""
    assert COMPONENT_TS.is_file(), f"expected addChart at {COMPONENT_TS}"


def test_at27_renderer_unit_checks() -> None:
    """Bar/line/pie/doughnut support, token colors, native chart XML in pptx."""
    result = _run_shell("npm run test:at27 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
