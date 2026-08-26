"""AT-29: addArchitectureNode() shared component tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_TS = ROOT / "apps" / "renderer" / "design_system" / "components" / "addArchitectureNode.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_at29_add_architecture_node_file_exists() -> None:
    """Maps to AT-29 done-when: labeled architecture-diagram node component exists."""
    assert COMPONENT_TS.is_file(), f"expected addArchitectureNode at {COMPONENT_TS}"


def test_at29_renderer_unit_checks() -> None:
    """Number badge + content card composition in pptx XML."""
    result = _run_shell("npm run test:at29 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
