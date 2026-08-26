"""AT-26: addDataTable() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addDataTable.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at26_add_data_table_file_exists() -> None:
    """Maps to AT-26 done-when: native editable table component exists."""
    assert COMPONENT_TS.is_file(), f"expected addDataTable at {COMPONENT_TS}"


def test_at26_renderer_unit_checks() -> None:
    """Header/body typography, token borders, native a:tbl markup in pptx XML."""
    result = _run_shell("npm run test:at26 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
