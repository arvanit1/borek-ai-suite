"""Branding token tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRANDING_TS = ROOT / "apps" / "renderer" / "design_system" / "tokens" / "branding.ts"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def test_branding_token_file_exists() -> None:
    """Maps to v2 §16 design-system/branding.ts — slide size, logo/footer/slide-number placement."""
    assert BRANDING_TS.is_file(), f"expected canonical branding tokens at {BRANDING_TS}"


def test_branding_renderer_unit_checks() -> None:
    """§16 slide dimensions, branding layout from spacing/typography/colors, CI guard."""
    result = _run_shell("npm run test:branding --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
