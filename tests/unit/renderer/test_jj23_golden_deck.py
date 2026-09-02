"""JJ-23: EXECUTIVE_SUMMARY_01 golden-deck fixtures wired into the AT-55 regression runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DECK_DIR = ROOT / "tests" / "golden_deck"
SUMMARY_DIR = GOLDEN_DECK_DIR / "summary"


def test_jj23_executive_summary_reference_exists() -> None:
    path = SUMMARY_DIR / "executive_summary_01.png"
    assert path.is_file()
    assert path.stat().st_size > 0


def test_jj23_executive_summary_golden_deck_regression() -> None:
    result = subprocess.run(
        "npm run test:jj23 --workspace borek-renderer",
        cwd=ROOT,
        check=False,
        shell=True,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
